import json
import logging
from typing import Optional

# Prefer Async client for FastAPI per official docs
# Reference: https://github.com/dodopayments/dodo-docs/blob/main/developer-resources/fastapi-boilerplate.mdx
from dodopayments import AsyncDodoPayments  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import (
    DODO_PAYMENTS_API_KEY,
    DODO_PAYMENTS_ENVIRONMENT,
    DODO_PAYMENTS_WEBHOOK_SECRET,
    FRONTEND_URL,
)
from ..database import get_db
from ..models import User
from ..rate_limiter import create_rate_limiter
from ..webhook_security import extract_svix_signing_key, verify_dodo_webhook

logger = logging.getLogger(__name__)

# Product IDs are provided by the frontend via env-configured mapping.
# Do not hardcode product IDs server-side.

# Initialize Dodo Payments client once
#
# IMPORTANT:
# The Dodo SDK expects environment values like "test_mode" or "live_mode".
# Some deployments accidentally set "live", which will crash the app at import time.
# We normalize common aliases to keep the service bootable.
if not DODO_PAYMENTS_API_KEY:
    logger.warning("DODO_PAYMENTS_API_KEY not set; billing endpoints will fail until configured")


def _normalize_dodo_environment(env: Optional[str]) -> str:
    value = (env or "test_mode").strip().lower()
    if value in {"live", "production", "prod"}:
        return "live_mode"
    if value in {"test", "sandbox", "staging", "dev", "development"}:
        return "test_mode"
    if value in {"test_mode", "live_mode"}:
        return value
    logger.warning(f"Unknown DODO environment '{env}', defaulting to test_mode")
    return "test_mode"


DODO_ENV = _normalize_dodo_environment(DODO_PAYMENTS_ENVIRONMENT)

try:
    dodo_client = AsyncDodoPayments(
        bearer_token=DODO_PAYMENTS_API_KEY or "",
        environment=DODO_ENV,
    )
except Exception as e:
    # Do NOT crash the whole API if billing is misconfigured
    logger.error(f"Failed to initialize Dodo client (env={DODO_ENV}): {e}")
    dodo_client = None

router = APIRouter(prefix="/billing", tags=["Billing"])
webhooks_router = APIRouter(tags=["Webhooks"])

# Rate limiter for payment webhooks - 100 requests per minute
rate_limit_billing_webhook = create_rate_limiter(
    limit=100,
    window_seconds=60,
    key_prefix="webhook_billing",
    use_ip=False,  # Global limit for all webhooks
)


class CheckoutRequest(BaseModel):
    product_id: str
    # Optional plan metadata for your app state
    plan: Optional[str] = None  # "solo" | "team" | "enterprise"
    billing_cycle: Optional[str] = None  # "monthly" | "yearly"
    quantity: int = 1
    # Optional override return url
    return_path: Optional[str] = None  # e.g. "/billing?checkout=success"

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("product_id is required")
        return v

    @field_validator("billing_cycle")
    @classmethod
    def validate_cycle(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"monthly", "yearly"}
        if v not in allowed:
            raise ValueError("billing_cycle must be 'monthly' or 'yearly' when provided")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


class UpdatePlanRequest(BaseModel):
    plan: str  # "solo", "team", "enterprise"


class CancelRequest(BaseModel):
    # When true, subscription remains active until the end of the current billing period
    cancel_at_period_end: bool = True
    # When true, immediately revoke access (set plan to null). Dodo will still process scheduled cancel if cancel_at_period_end=True
    revoke_access_now: bool = False


class ChangePlanRequest(BaseModel):
    product_id: str
    quantity: int = 1
    proration_billing_mode: str = "prorated_immediately"  # per docs
    # optional local plan update for app gating ("solo" | "team" | "enterprise")
    plan: Optional[str] = None


# Plan limits configuration
PLAN_LIMITS = {
    "solo": {"clients": 10, "contracts": 10, "schedules": 10},
    "team": {"clients": 50, "contracts": 50, "schedules": 50},
    "enterprise": {"clients": 999999, "contracts": 999999, "schedules": 999999},  # Unlimited
}

# Default limits for users without a plan (should not happen after onboarding)
NO_PLAN_LIMITS = {"clients": 0, "contracts": 0, "schedules": 0}


@router.get("/usage-stats")
async def get_usage_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get usage statistics for the current billing period (30 days from subscription date)"""
    from datetime import datetime, timedelta

    from ..models import Client, Contract, Schedule

    now = datetime.utcnow()

    # Use subscription_start_date if available, otherwise fall back to created_at
    subscription_start = user.subscription_start_date or user.created_at or now

    # Calculate billing period based on subscription date (30-day cycles)
    days_since_start = (now - subscription_start).days
    cycles_passed = days_since_start // 30

    # Current billing period start and end
    period_start = subscription_start + timedelta(days=cycles_passed * 30)
    period_end = subscription_start + timedelta(days=(cycles_passed + 1) * 30)

    # Count clients created this billing period
    clients_count = (
        db.query(Client)
        .filter(
            Client.user_id == user.id,
            Client.created_at >= period_start,
            Client.created_at < period_end,
        )
        .count()
    )

    # Count contracts created this billing period
    contracts_count = (
        db.query(Contract)
        .filter(
            Contract.user_id == user.id,
            Contract.created_at >= period_start,
            Contract.created_at < period_end,
        )
        .count()
    )

    # Count schedules this billing period
    schedules_count = (
        db.query(Schedule)
        .filter(
            Schedule.user_id == user.id,
            Schedule.scheduled_date >= period_start,
            Schedule.scheduled_date < period_end,
        )
        .count()
    )

    # Get plan limits (no plan = no access until they select one)
    plan = user.plan
    if plan:
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["solo"])
    else:
        limits = NO_PLAN_LIMITS

    # Reset date is the end of current billing period (30 days from subscription anniversary)
    reset_date = period_end

    return {
        "plan": plan,
        "usage": {
            "clients": {"current": clients_count, "limit": limits["clients"]},
            "contracts": {"current": contracts_count, "limit": limits["contracts"]},
            "schedules": {"current": schedules_count, "limit": limits["schedules"]},
        },
        "reset_date": reset_date.isoformat(),
    }


@router.post("/update-plan")
async def update_user_plan(
    body: UpdatePlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually update user's plan. Used after successful checkout verification.
    In production, this should verify the subscription status with Dodo Payments.
    """
    allowed_plans = {"solo", "team", "enterprise"}
    if body.plan not in allowed_plans:
        raise HTTPException(
            status_code=400, detail=f"Invalid plan. Must be one of: {allowed_plans}"
        ) from e

    user.plan = body.plan
    db.commit()
    logger.info(f"User {user.id} plan manually updated to {body.plan}")
    return {"message": f"Plan updated to {body.plan}", "plan": body.plan}


@router.get("/debug/find-user")
async def debug_find_user(
    firebase_uid: str = None, email: str = None, db: Session = Depends(get_db)
):
    """Debug endpoint to find users by firebase_uid or email"""
    results = {}

    if firebase_uid:
        user_by_uid = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        results["by_firebase_uid"] = {
            "found": user_by_uid is not None,
            "user_id": user_by_uid.id if user_by_uid else None,
            "email": user_by_uid.email if user_by_uid else None,
            "plan": user_by_uid.plan if user_by_uid else None,
        }

    if email:
        user_by_email = db.query(User).filter(User.email == email).first()
        results["by_email"] = {
            "found": user_by_email is not None,
            "user_id": user_by_email.id if user_by_email else None,
            "firebase_uid": user_by_email.firebase_uid if user_by_email else None,
            "plan": user_by_email.plan if user_by_email else None,
        }

    # Also show recent users for debugging
    recent_users = db.query(User).order_by(User.id.desc()).limit(5).all()
    results["recent_users"] = [
        {"id": u.id, "email": u.email, "firebase_uid": u.firebase_uid, "plan": u.plan}
        for u in recent_users
    ]

    return results


@router.get("/debug/user-status")
async def debug_user_status(
    user: User = Depends(get_current_user),
):
    """Debug endpoint to check user's current subscription status"""
    return {
        "user_id": user.id,
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "plan": user.plan,
        "subscription_status": user.subscription_status,
        "subscription_id": getattr(user, "subscription_id", None),
        "subscription_start_date": (
            user.subscription_start_date.isoformat() if user.subscription_start_date else None
        ),
        "last_payment_date": user.last_payment_date.isoformat() if user.last_payment_date else None,
        "next_billing_date": user.next_billing_date.isoformat() if user.next_billing_date else None,
        "billing_cycle": user.billing_cycle,
    }


@router.post("/activate-plan")
async def manually_activate_plan(
    request: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Manually activate a plan for a user (temporary endpoint for troubleshooting)
    """
    plan = request.get("plan")
    billing_cycle = request.get("billing_cycle", "yearly")

    if not plan or plan not in ["solo", "team"]:
        raise HTTPException(status_code=400, detail="Invalid plan")

    try:
        from datetime import datetime, timedelta

        # Update user plan and subscription details
        current_user.plan = plan
        current_user.subscription_status = "active"
        current_user.last_payment_date = datetime.utcnow()
        current_user.billing_cycle = billing_cycle

        # Set subscription start date if not already set
        if not current_user.subscription_start_date:
            current_user.subscription_start_date = datetime.utcnow()
            current_user.clients_this_month = 0
            current_user.month_reset_date = datetime.utcnow() + timedelta(days=30)

        # Calculate next billing date
        if billing_cycle == "yearly":
            current_user.next_billing_date = datetime.utcnow() + timedelta(days=365)
        else:
            current_user.next_billing_date = datetime.utcnow() + timedelta(days=30)

        db.commit()

        logger.info(f"✅ Manually activated {plan} plan for user {current_user.id}")

        return {
            "message": "Plan activated successfully",
            "plan": plan,
            "billing_cycle": billing_cycle,
            "subscription_status": "active",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to activate plan for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate plan") from e


@router.get("/current-plan")
async def get_current_plan(
    user: User = Depends(get_current_user),
):
    """Get the current user's plan and billing info"""
    from datetime import datetime, timedelta

    # Calculate next billing date based on subscription start (30-day cycles)
    subscription_start = user.subscription_start_date or user.created_at or datetime.utcnow()
    now = datetime.utcnow()
    days_since_start = (now - subscription_start).days
    cycles_passed = days_since_start // 30
    next_billing_date = subscription_start + timedelta(days=(cycles_passed + 1) * 30)

    return {
        "plan": user.plan,
        "subscription_status": user.subscription_status,
        "subscription_start_date": subscription_start.isoformat() if subscription_start else None,
        "next_billing_date": next_billing_date.isoformat(),
    }


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
):
    """
    Create a Dodo Payments Dynamic Checkout session for the selected plan.
    Security:
      - Requires Firebase auth (get_current_user)
      - Uses server-side API key from environment
    Docs:
      - Create Checkout Session: https://github.com/dodopayments/dodo-docs/blob/main/developer-resources/subscription-integration-guide.mdx
      - FastAPI example: https://github.com/dodopayments/dodo-docs/blob/main/developer-resources/fastapi-boilerplate.mdx
    """
    if not DODO_PAYMENTS_API_KEY or dodo_client is None:
        raise HTTPException(status_code=500, detail="Billing not configured")

    # Frontend supplies product_id from env; validate presence
    product_id = body.product_id
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    return_url = f"{FRONTEND_URL.rstrip('/')}{body.return_path or '/checkout/success'}"

    # Build metadata to link back to your user
    metadata = {
        "firebase_uid": user.firebase_uid,
        "internal_user_id": str(user.id),
        "selected_plan": body.plan or "unknown",
        "billing_cycle": body.billing_cycle or "unknown",
    }

    # Prepare customer prefill
    customer = {
        "email": user.email,
        "name": user.full_name or "",
    }

    try:
        session = await dodo_client.checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": body.quantity}],
            customer=customer,
            # Optional trial config example:
            # subscription_data={"trial_period_days": 3},
            metadata=metadata,
            return_url=return_url,
        )
        # According to docs, response contains `checkout_url` and `session_id`
        checkout_url = (
            getattr(session, "checkout_url", None)
            or getattr(session, "url", None)
            or session.get("checkout_url")
        )
        session_id = getattr(session, "session_id", None) or session.get("session_id")
        if not checkout_url:
            logger.error(f"Unexpected session response: {session}")
            raise HTTPException(status_code=502, detail="Invalid checkout session response")

        logger.info(
            f"Checkout session created for user_id={user.id} plan={body.plan} cycle={body.billing_cycle} session_id={session_id}"
        )
        return {"checkout_url": checkout_url, "session_id": session_id}

    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=400, detail="Failed to create checkout session") from e


@router.post("/cancel")
async def cancel_subscription(
    body: CancelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Schedule or request cancellation on Dodo; optionally set app plan to null immediately.
    Docs:
      - Cancel at period end via PATCH: https://docs.dodopayments.com/api-reference/subscriptions/patch-subscriptions
      - Webhook 'subscription.cancelled' will be sent when cancellation takes effect
    """
    if not DODO_PAYMENTS_API_KEY:
        raise HTTPException(status_code=500, detail="Billing not configured")

    if not getattr(user, "subscription_id", None):
        raise HTTPException(status_code=400, detail="No active subscription on file for this user")

    try:
        # Schedule cancellation or cancel immediately if supported by status patch
        # Per docs, scheduling uses cancel_at_next_billing_date flag.
        await dodo_client.subscriptions.update(
            subscription_id=user.subscription_id,
            cancel_at_next_billing_date=body.cancel_at_period_end,
        )

        if body.revoke_access_now:
            user.plan = None
            db.commit()
            logger.info(f"User {user.id} plan revoked locally on cancel request")

        return {
            "status": "ok",
            "scheduled_at_period_end": body.cancel_at_period_end,
            "access_revoked": body.revoke_access_now,
        }
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(status_code=400, detail="Failed to cancel subscription") from e


@router.post("/change-plan")
async def change_subscription_plan(
    body: ChangePlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change plan for an active subscription (paid→paid) using Dodo Change Plan API.
    Charges are handled by Dodo per proration_billing_mode; no checkout required.
    Docs:
      - Change Plan: https://docs.dodopayments.com/api-reference/subscriptions/change-plan
      - Proration guidance: https://docs.dodopayments.com/developer-resources/subscription-upgrade-downgrade
    """
    if not DODO_PAYMENTS_API_KEY:
        raise HTTPException(status_code=500, detail="Billing not configured")

    if not getattr(user, "subscription_id", None):
        raise HTTPException(status_code=400, detail="No active subscription on file for this user")

    if not body.product_id:
        raise HTTPException(status_code=400, detail="product_id is required")

    try:
        await dodo_client.subscriptions.change_plan(
            subscription_id=user.subscription_id,
            product_id=body.product_id,
            quantity=body.quantity,
            proration_billing_mode=body.proration_billing_mode,
        )
        # Optionally update local plan immediately for app gating; webhook will correct if needed
        if body.plan:
            user.plan = body.plan
            db.commit()
            logger.info(f"User {user.id} plan locally updated to {body.plan} after change_plan")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to change plan: {e}")
        raise HTTPException(status_code=400, detail="Failed to change subscription plan") from e


# No product-to-plan mapping on backend; plan is derived from metadata set at checkout creation.

# ======== Payment Method & Payment History (per-user, secure) ========


class PaymentMethodResponse(BaseModel):
    dodo_customer_id: Optional[str] = None
    payment_method: Optional[Dict] = (
        None  # {"id","type","brand","last4","exp_month","exp_year","is_default"}
    )


class PaymentItem(BaseModel):
    id: str
    created_at: Optional[str] = None
    description: Optional[str] = None
    amount: float
    currency: str
    status: str
    invoice_available: bool = False


class BillingAddressResponse(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = None
    country: Optional[str] = None
    updated_at: Optional[str] = None


class PaymentsResponse(BaseModel):
    payments: list[PaymentItem]


def _major_amount(amount_lowest: Optional[int], currency: Optional[str]) -> float:
    if amount_lowest is None:
        return 0.0
    # Convert from lowest denomination to major units
    c = (currency or "USD").upper()
    # Common currencies with 100 minor units
    if c in {"USD", "EUR", "GBP", "CAD", "AUD", "NZD", "SGD", "MXN"}:
        return round(amount_lowest / 100.0, 2)
    # JPY is zero-decimal
    if c in {"JPY", "KRW"}:
        return float(amount_lowest)
    # Default to 100 minor units
    return round(amount_lowest / 100.0, 2)


@router.get("/payment-method", response_model=PaymentMethodResponse)
async def get_user_payment_method(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the user's default payment method metadata (brand, last4, exp) masked.
    Stores only non-PCI data. Falls back to Dodo API lookup by dodo_customer_id.
    """
    if not DODO_PAYMENTS_API_KEY or dodo_client is None:
        # Return any locally stored metadata if billing not configured
        return PaymentMethodResponse(
            dodo_customer_id=getattr(user, "dodo_customer_id", None),
            payment_method=(
                {
                    "id": getattr(user, "dodo_default_payment_method_id", None),
                    "type": getattr(user, "dodo_payment_method_type", None) or "card",
                    "brand": getattr(user, "dodo_payment_method_brand", None),
                    "last4": getattr(user, "dodo_payment_method_last4", None),
                    "exp_month": getattr(user, "dodo_payment_method_exp_month", None),
                    "exp_year": getattr(user, "dodo_payment_method_exp_year", None),
                    "is_default": True,
                }
                if getattr(user, "dodo_payment_method_last4", None)
                else None
            ),
        )

    # If we already have local masked metadata, return it first
    if getattr(user, "dodo_payment_method_last4", None):
        return PaymentMethodResponse(
            dodo_customer_id=getattr(user, "dodo_customer_id", None),
            payment_method={
                "id": getattr(user, "dodo_default_payment_method_id", None),
                "type": getattr(user, "dodo_payment_method_type", None) or "card",
                "brand": getattr(user, "dodo_payment_method_brand", None),
                "last4": getattr(user, "dodo_payment_method_last4", None),
                "exp_month": getattr(user, "dodo_payment_method_exp_month", None),
                "exp_year": getattr(user, "dodo_payment_method_exp_year", None),
                "is_default": True,
            },
        )

    # Otherwise attempt to pull from Dodo customer vault
    customer_id = getattr(user, "dodo_customer_id", None)
    if not customer_id:
        # No Dodo customer on file yet
        return PaymentMethodResponse(dodo_customer_id=None, payment_method=None)

    try:
        pm_list = await dodo_client.customers.retrieve_payment_methods(customer_id)
        items = getattr(pm_list, "items", []) or getattr(pm_list, "data", []) or []
        if not items:
            return PaymentMethodResponse(dodo_customer_id=customer_id, payment_method=None)

        # Prefer the first or a flagged default
        method = None
        for it in items:
            if getattr(it, "is_default", False) or (getattr(it, "default", False)):
                method = it
                break
        if method is None:
            method = items[0]

        # Extract card details safely
        card = getattr(method, "card", None) or {}
        brand = getattr(card, "brand", None) or getattr(method, "brand", None)
        last4 = getattr(card, "last4", None) or getattr(method, "last4", None)
        exp_month = getattr(card, "exp_month", None) or getattr(method, "exp_month", None)
        exp_year = getattr(card, "exp_year", None) or getattr(method, "exp_year", None)
        pm_type = getattr(method, "type", None) or "card"
        pm_id = getattr(method, "payment_method_id", None) or getattr(method, "id", None)

        # Persist non-PCI metadata
        user.dodo_default_payment_method_id = pm_id
        user.dodo_payment_method_type = pm_type
        user.dodo_payment_method_brand = brand
        user.dodo_payment_method_last4 = last4
        user.dodo_payment_method_exp_month = exp_month
        user.dodo_payment_method_exp_year = exp_year
        db.commit()

        return PaymentMethodResponse(
            dodo_customer_id=customer_id,
            payment_method={
                "id": pm_id,
                "type": pm_type,
                "brand": brand,
                "last4": last4,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "is_default": True,
            },
        )
    except Exception as e:
        logger.error(f"Failed to retrieve payment methods for user {user.id}: {e}")
        return PaymentMethodResponse(dodo_customer_id=customer_id, payment_method=None)


@router.get("/billing-address", response_model=BillingAddressResponse)
async def get_billing_address(
    user: User = Depends(get_current_user),
):
    return BillingAddressResponse(
        street=getattr(user, "billing_street", None),
        city=getattr(user, "billing_city", None),
        state=getattr(user, "billing_state", None),
        zipcode=getattr(user, "billing_zipcode", None),
        country=getattr(user, "billing_country", None),
        updated_at=(
            getattr(user, "billing_updated_at", None).isoformat()
            if getattr(user, "billing_updated_at", None)
            else None
        ),
    )


@router.get("/payments", response_model=PaymentsResponse)
async def get_user_payments(
    user: User = Depends(get_current_user),
):
    """
    List payments for the authenticated user.
    Filters by Dodo customer id and/or metadata.internal_user_id to ensure per-user isolation.
    """
    if not DODO_PAYMENTS_API_KEY or dodo_client is None:
        return PaymentsResponse(payments=[])

    cust_id = getattr(user, "dodo_customer_id", None)
    results: list[PaymentItem] = []
    try:
        # Auto-paginating async iterator
        async for pay in dodo_client.payments.list():
            # Narrow scope to this user securely
            pay_meta = getattr(pay, "metadata", {}) or {}
            internal_user_id = str(pay_meta.get("internal_user_id") or "")
            pay_customer = getattr(pay, "customer", None)
            pay_customer_id = None
            if pay_customer:
                pay_customer_id = getattr(pay_customer, "id", None) or getattr(
                    pay_customer, "customer_id", None
                )

            if cust_id and pay_customer_id and pay_customer_id != cust_id:
                continue
            if internal_user_id and internal_user_id != str(user.id):
                continue
            if not cust_id and not internal_user_id:
                # If neither marker exists, skip for safety
                continue

            amount_lowest = getattr(pay, "amount", None) or getattr(pay, "amount_lowest_unit", None)
            currency = getattr(pay, "currency", None) or "USD"
            status = getattr(pay, "status", None) or "paid"
            description = getattr(pay, "description", None) or getattr(
                pay, "statement_descriptor", None
            )
            created_at = getattr(pay, "created_at", None)
            pay_id = getattr(pay, "id", None) or getattr(pay, "payment_id", None)

            # Check if invoice is available
            has_invoice = True if pay_id else False

            results.append(
                PaymentItem(
                    id=str(pay_id),
                    created_at=str(created_at) if created_at else None,
                    description=description,
                    amount=_major_amount(amount_lowest, currency),
                    currency=currency,
                    status=status,
                    invoice_available=has_invoice,
                )
            )
    except Exception as e:
        logger.error(f"Failed to list payments for user {user.id}: {e}")
        return PaymentsResponse(payments=[])

    # Sort newest first if dates exist
    results.sort(key=lambda x: x.created_at or "", reverse=True)
    return PaymentsResponse(payments=results)


@router.get("/invoices/{payment_id}/download")
async def download_payment_invoice_pdf(
    payment_id: str,
    user: User = Depends(get_current_user),
):
    """
    Securely stream the PDF invoice for a given payment_id if it belongs to the current user.
    Validates ownership by scanning the user's own payments in-memory before requesting the PDF.
    """
    if not DODO_PAYMENTS_API_KEY or dodo_client is None:
        raise HTTPException(status_code=500, detail="Billing not configured") from e

    # Ownership check
    is_owned = False
    try:
        cust_id = getattr(user, "dodo_customer_id", None)
        async for pay in dodo_client.payments.list():
            pid = getattr(pay, "id", None) or getattr(pay, "payment_id", None)
            if not pid or str(pid) != payment_id:
                continue
            pay_meta = getattr(pay, "metadata", {}) or {}
            internal_user_id = str(pay_meta.get("internal_user_id") or "")
            pay_customer = getattr(pay, "customer", None)
            pay_customer_id = None
            if pay_customer:
                pay_customer_id = getattr(pay_customer, "id", None) or getattr(
                    pay_customer, "customer_id", None
                )

            if cust_id and pay_customer_id and pay_customer_id != cust_id:
                continue
            if internal_user_id and internal_user_id != str(user.id):
                continue
            is_owned = True
            break
    except Exception as e:
        logger.error(f"Failed during ownership verification for payment {payment_id}: {e}")
        raise HTTPException(status_code=400, detail="Unable to verify payment ownership") from e

    if not is_owned:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        # Retrieve PDF content via Dodo SDK
        invoice_file = await dodo_client.invoices.payments.retrieve(payment_id)
        content = None

        if hasattr(invoice_file, "read"):
            content = invoice_file.read()
        elif hasattr(invoice_file, "content"):
            content = invoice_file.content
        elif hasattr(invoice_file, "to_bytes"):
            content = invoice_file.to_bytes()

        if content is None:
            # As a last resort, try attribute commonly used for async responses
            content = getattr(invoice_file, "body", None)

        if not content:
            logger.error(f"Invoice content empty for payment {payment_id}")
            raise HTTPException(status_code=502, detail="Failed to fetch invoice")

        from fastapi import Response as FastAPIResponse

        return FastAPIResponse(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="invoice_{payment_id}.pdf"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download invoice for payment {payment_id}: {e}")
        raise HTTPException(status_code=400, detail="Failed to download invoice") from e


@webhooks_router.post("/webhooks/dodopayments/bypass")
async def bypass_signature_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Temporary webhook endpoint that bypasses signature verification.
    Use this to process webhooks while we debug the signature issue.
    """
    try:
        raw_body = await request.body()
        webhook_id = request.headers.get("webhook-id", "unknown")
        timestamp = request.headers.get("webhook-timestamp", "")
        signature = request.headers.get("webhook-signature", "")

        logger.info(f"🔓 BYPASS: Processing webhook {webhook_id} without signature verification")
        logger.info(f"🔓 Signature: {signature}")
        logger.info(f"🔓 Timestamp: {timestamp}")
        logger.info(f"🔓 Body length: {len(raw_body)}")

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            return {"error": "Invalid JSON payload"}

        event_type = event.get("type")
        data = event.get("data") or {}

        logger.info(f"🔓 Event type: {event_type}")
        logger.info(f"🔓 Data keys: {list(data.keys())}")

        # Log metadata for debugging
        meta = data.get("metadata") or {}
        if meta:
            logger.info(f"🔓 Metadata: {meta}")

        # Process subscription events
        if event_type in (
            "subscription.active",
            "subscription.renewed",
            "subscription.plan_changed",
            "checkout.session.completed",
        ):
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")
            selected_plan = meta.get("selected_plan")
            billing_cycle = meta.get("billing_cycle")

            logger.info(
                f"🔓 Processing {event_type} for firebase_uid: {firebase_uid}, plan: {selected_plan}"
            )

            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user and selected_plan and selected_plan != "unknown":
                from datetime import datetime, timedelta

                old_plan = user.plan
                user.plan = selected_plan
                user.subscription_status = "active"
                user.last_payment_date = datetime.utcnow()

                if billing_cycle and billing_cycle != "unknown":
                    user.billing_cycle = billing_cycle
                    if billing_cycle == "yearly":
                        user.next_billing_date = datetime.utcnow() + timedelta(days=365)
                    else:
                        user.next_billing_date = datetime.utcnow() + timedelta(days=30)
                else:
                    user.next_billing_date = datetime.utcnow() + timedelta(days=30)

                if not user.subscription_start_date:
                    user.subscription_start_date = datetime.utcnow()
                    user.clients_this_month = 0
                    user.month_reset_date = datetime.utcnow() + timedelta(days=30)

                db.commit()

                logger.info(
                    f"🔓 SUCCESS: Updated user {user.id} plan from {old_plan} to {selected_plan}"
                )

                return {
                    "status": "processed",
                    "message": f"Plan updated from {old_plan} to {selected_plan}",
                    "user_id": user.id,
                    "webhook_id": webhook_id,
                }
            else:
                logger.warning("🔓 Could not process webhook - user not found or invalid plan")
                return {"status": "skipped", "reason": "user not found or invalid plan"}

        return {"status": "received", "event_type": event_type}

    except Exception as e:
        logger.error(f"🔓 BYPASS webhook error: {e}")
        return {"error": str(e)}


@webhooks_router.post("/webhooks/dodopayments/test-byte-perfect")
async def test_byte_perfect_signature():
    """
    Test the byte-perfect signature implementation using Standard Webhooks (Svix) format:
    signed_message = webhook-id.webhook-timestamp.payload
    signature = base64(HMAC_SHA256(signing_key_bytes, signed_message_bytes))
    """
    import base64
    import hashlib
    import hmac
    import os

    from ..webhook_security import extract_svix_signing_key

    # Data from recent logs (example placeholders)
    webhook_id = "msg_example123"
    timestamp = "1770057255"
    received_signature = "OkPW+QrUpFRf6tFENpZeI2ZXYWEWCbZaHZmEq0+S5tY="

    # Get actual webhook secret
    webhook_secret = os.getenv("DODO_PAYMENTS_WEBHOOK_SECRET", "")

    # Sample body as bytes (approximate)
    sample_body = b'{"business_id":"bus_OumfAar4K7irg6ZTZlqcD","data":{"billing":{"city":"Camden","country":"US","state":"Delaware","street":"2140 S Dupont Hwy, 2140 South Dupont Highway","zipcode":"19934"},"brand_id":"brand_123","metadata":{"firebase_uid":"test_uid","selected_plan":"solo","billing_cycle":"yearly"}}}'

    # Svix canonical: id.timestamp.body (all bytes, no JSON reserialization)
    signed_payload = (
        webhook_id.encode("utf-8") + b"." + timestamp.encode("utf-8") + b"." + sample_body
    )

    # Test with different secret formats (only correct: base64 decode after whsec_)
    secrets_to_test = [
        ("env_secret", webhook_secret),
        (
            "env_without_whsec",
            webhook_secret[6:] if webhook_secret.startswith("whsec_") else webhook_secret,
        ),
        ("hardcoded_full", "whsec_iCYnlyl4QjPRL9Bj1Vka0pmX22FcNyEz"),
        ("hardcoded_no_prefix", "iCYnlyl4QjPRL9Bj1Vka0pmX22FcNyEz"),
    ]

    results = {}

    for secret_name, secret in secrets_to_test:
        if not secret:
            continue

        try:
            key_bytes = extract_svix_signing_key(secret)
            expected_signature = base64.b64encode(
                hmac.new(key_bytes, signed_payload, hashlib.sha256).digest()
            ).decode("utf-8")

            results[secret_name] = {
                "secret_prefix": (
                    (secret[:10] + "...")
                    if isinstance(secret, str) and len(secret) > 10
                    else (secret if isinstance(secret, str) else "bytes")
                ),
                "expected_signature": expected_signature,
                "matches_received": expected_signature == received_signature,
            }
        except Exception as e:
            results[secret_name] = {"error": str(e)}

    return {
        "method": "BYTE-PERFECT: id.encode()+b'.'+timestamp.encode()+b'.'+raw_body",
        "webhook_id": webhook_id,
        "timestamp": timestamp,
        "received_signature": received_signature,
        "sample_body_length": len(sample_body),
        "signed_payload_length": len(signed_payload),
        "env_secret_set": bool(webhook_secret),
        "results": results,
        "note": "Look for 'matches_received': true to confirm correct secret handling (base64 decode after whsec_)",
    }


@webhooks_router.post("/webhooks/dodopayments/debug")
@webhooks_router.post("/api/payments/dodo/webhook/debug")  # Debug alias
async def debug_dodo_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Debug endpoint to help troubleshoot Dodo webhook signature issues.
    This endpoint logs all webhook details without signature verification.
    """
    import base64
    import hashlib
    import hmac

    try:
        raw_body = await request.body()
        headers = dict(request.headers)

        # Log all relevant information
        logger.info("🔍 DEBUG: Dodo webhook received")
        logger.info(f"🔍 Headers: {headers}")
        logger.info(f"🔍 Body length: {len(raw_body)}")
        logger.info(f"🔍 Body (first 500 chars): {raw_body[:500]}")

        # Check if we have the webhook secret
        webhook_secret = DODO_PAYMENTS_WEBHOOK_SECRET
        logger.info(f"🔍 Webhook secret configured: {'Yes' if webhook_secret else 'No'}")

        if webhook_secret:
            signature = headers.get("webhook-signature", "")
            timestamp = headers.get("webhook-timestamp", "")

            logger.info(f"🔍 Received signature: {signature}")
            logger.info(f"🔍 Timestamp: {timestamp}")

            # Test different secret variants
            secrets_to_try = [webhook_secret]
            if webhook_secret.startswith("whsec_"):
                secrets_to_try.append(webhook_secret[6:])

            for secret_variant in secrets_to_try:
                logger.info(f"🔍 Testing secret variant: {secret_variant[:10]}...")

                # First: Svix/Standard Webhooks canonical check using id.timestamp.payload and base64(HMAC-SHA256)
                signing_key = extract_svix_signing_key(secret_variant)
                signed_message_bytes = (
                    headers.get("webhook-id", "").encode("utf-8")
                    + b"."
                    + timestamp.encode("utf-8")
                    + b"."
                    + raw_body
                )
                expected_svix = base64.b64encode(
                    hmac.new(signing_key, signed_message_bytes, hashlib.sha256).digest()
                ).decode("utf-8")
                signature_without_prefix = (
                    signature[3:] if signature.startswith("v1,") else signature
                )
                logger.info(f"🔍 svix id.ts.body expected base64: {expected_svix}")
                if expected_svix == signature_without_prefix:
                    logger.info(
                        "🎯 MATCH FOUND: svix id.timestamp.body base64 matches v1 signature!"
                    )

                # Legacy/debug payload constructions
                payloads_to_test = [
                    ("raw_body", raw_body),
                ]

                if timestamp:
                    payloads_to_test.extend(
                        [
                            (
                                "timestamp.body",
                                f"{timestamp}.{raw_body.decode('utf-8', errors='ignore')}".encode(),
                            ),
                            (
                                "timestamp+body",
                                f"{timestamp}{raw_body.decode('utf-8', errors='ignore')}".encode(),
                            ),
                        ]
                    )

                for payload_name, payload in payloads_to_test:
                    expected_hex = hmac.new(
                        secret_variant.encode("utf-8"), payload, hashlib.sha256
                    ).hexdigest()
                    expected_base64 = base64.b64encode(
                        hmac.new(secret_variant.encode("utf-8"), payload, hashlib.sha256).digest()
                    ).decode("utf-8")

                    logger.info(f"🔍 {payload_name} - Expected hex: {expected_hex}")
                    logger.info(f"🔍 {payload_name} - Expected base64: {expected_base64}")

                    # Check if signature matches any format
                    if signature.startswith("v1,"):
                        signature_without_prefix = signature[3:]
                        logger.info(
                            f"🔍 {payload_name} - Signature without v1 prefix: {signature_without_prefix}"
                        )

                        if expected_hex == signature_without_prefix:
                            logger.info(f"🎯 MATCH FOUND: {payload_name} hex matches v1 signature!")
                        elif expected_base64 == signature_without_prefix:
                            logger.info(
                                f"🎯 MATCH FOUND: {payload_name} base64 matches v1 signature!"
                            )

                    # Also check direct matches
                    if expected_hex == signature:
                        logger.info(f"🎯 DIRECT MATCH: {payload_name} hex matches signature!")
                    elif expected_base64 == signature:
                        logger.info(f"🎯 DIRECT MATCH: {payload_name} base64 matches signature!")

        return {"status": "debug_complete", "message": "Check logs for signature analysis"}

    except Exception as e:
        logger.error(f"🔍 DEBUG: Error processing webhook: {e}")
        return {"status": "debug_error", "error": str(e)}


@webhooks_router.post("/webhooks/dodopayments/manual-fix-from-logs")
async def manual_fix_from_webhook_logs(request: Request, db: Session = Depends(get_db)):
    """
    Extract user info from webhook logs and manually fix their plan.
    Use this when webhook signature verification fails but we can see the webhook data in logs.
    """
    try:
        # Get the webhook data (this endpoint doesn't verify signature)
        raw_body = await request.body()
        event = json.loads(raw_body.decode("utf-8"))

        data = event.get("data") or {}
        meta = data.get("metadata") or {}

        firebase_uid = meta.get("firebase_uid")
        selected_plan = meta.get("selected_plan")
        billing_cycle = meta.get("billing_cycle")

        if not firebase_uid:
            return {"error": "No firebase_uid found in webhook metadata"}

        if not selected_plan or selected_plan == "unknown":
            return {"error": "No valid selected_plan found in webhook metadata"}

        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            return {"error": f"User not found for firebase_uid: {firebase_uid}"}

        # Update user plan and subscription status
        from datetime import datetime, timedelta

        old_plan = user.plan
        user.plan = selected_plan
        user.subscription_status = "active"
        user.last_payment_date = datetime.utcnow()

        if not user.subscription_start_date:
            user.subscription_start_date = datetime.utcnow()
            user.clients_this_month = 0
            user.month_reset_date = datetime.utcnow() + timedelta(days=30)

        # Set billing cycle and next billing date
        if billing_cycle and billing_cycle != "unknown":
            user.billing_cycle = billing_cycle
            if billing_cycle == "yearly":
                user.next_billing_date = datetime.utcnow() + timedelta(days=365)
            else:
                user.next_billing_date = datetime.utcnow() + timedelta(days=30)
        else:
            user.next_billing_date = datetime.utcnow() + timedelta(days=30)

        db.commit()

        logger.info(
            f"🔧 MANUAL FIX FROM LOGS: Updated user {user.id} plan from {old_plan} to {selected_plan}"
        )

        return {
            "success": True,
            "message": f"User plan updated from {old_plan} to {selected_plan}",
            "user_id": user.id,
            "email": user.email,
            "firebase_uid": firebase_uid,
            "billing_cycle": billing_cycle,
        }

    except Exception as e:
        logger.error(f"❌ Manual fix from logs error: {e}")
        return {"error": str(e)}


@webhooks_router.post("/webhooks/dodopayments/manual-fix")
async def manual_fix_user_plan(request: Request, db: Session = Depends(get_db)):
    """
    Temporary endpoint to manually fix user plan when webhook fails.
    This should only be used for debugging/emergency fixes.
    """
    try:
        data = await request.json()
        firebase_uid = data.get("firebase_uid")
        plan = data.get("plan")

        if not firebase_uid or not plan:
            return {"error": "firebase_uid and plan are required"}

        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            return {"error": "User not found"}

        # Update user plan and subscription status
        from datetime import datetime, timedelta

        old_plan = user.plan
        user.plan = plan
        user.subscription_status = "active"
        user.last_payment_date = datetime.utcnow()

        if not user.subscription_start_date:
            user.subscription_start_date = datetime.utcnow()
            user.clients_this_month = 0
            user.month_reset_date = datetime.utcnow() + timedelta(days=30)

        # Set next billing date (default to monthly)
        user.next_billing_date = datetime.utcnow() + timedelta(days=30)

        db.commit()

        logger.info(f"🔧 MANUAL FIX: Updated user {user.id} plan from {old_plan} to {plan}")

        return {
            "success": True,
            "message": f"User plan updated from {old_plan} to {plan}",
            "user_id": user.id,
            "email": user.email,
        }

    except Exception as e:
        logger.error(f"❌ Manual fix error: {e}")
        return {"error": str(e)}


@webhooks_router.post("/webhooks/dodopayments")
@webhooks_router.post("/api/payments/dodo/webhook")  # Alias for Dodo's configured webhook URL
@webhooks_router.post("/api/payments/dodo/webhook")  # Alias for Dodo's configured webhook URL
async def handle_dodopayments_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_billing_webhook),
):
    """
    Verify signature and process subscription lifecycle events - Rate limited to 100 requests per minute.

    Security:
      - HMAC-SHA256 signature verification with constant-time comparison
      - Timestamp validation to prevent replay attacks
      - Rate limiting to prevent abuse

    Headers:
      - 'webhook-signature': 'v1,{base64(hmac_sha256(webhook-id.webhook-timestamp.payload))}'
      - 'webhook-id': Unique webhook ID for idempotency
      - 'webhook-timestamp': Unix timestamp (seconds)
    """
    if not DODO_PAYMENTS_WEBHOOK_SECRET:
        logger.error("❌ DODO_PAYMENTS_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured") from e

    # Log webhook secret length for debugging
    logger.info(f"🔑 Webhook secret configured, length = {len(DODO_PAYMENTS_WEBHOOK_SECRET)}")

    # Verify webhook signature using centralized security module
    is_valid, raw_body = await verify_dodo_webhook(
        request, DODO_PAYMENTS_WEBHOOK_SECRET, raise_on_failure=True
    )

    webhook_id = request.headers.get("webhook-id", "unknown")
    webhook_timestamp = request.headers.get("webhook-timestamp", "")

    # CRITICAL: Check for duplicate webhook processing (idempotency)
    # This prevents double-charging users if the same webhook is received multiple times
    from ..cache import cache

    idempotency_key = f"webhook_processed:{webhook_id}"

    if cache.get(idempotency_key):
        logger.info(f"🔄 Webhook {webhook_id} already processed, skipping (idempotency)")
        return {"status": "already_processed", "webhook_id": webhook_id}

    # Mark webhook as being processed (24 hour TTL)
    cache.set(idempotency_key, True, ttl=86400)

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e

    event_type = event.get("type")
    data = event.get("data") or {}
    logger.info(f"🔔 Webhook received id={webhook_id} ts={webhook_timestamp} type={event_type}")
    logger.info(f"📋 Webhook data keys: {list(data.keys())}")

    # Log metadata for debugging
    meta = data.get("metadata") or {}
    if meta:
        logger.info(f"🏷️ Webhook metadata: {meta}")
    else:
        logger.warning("⚠️ No metadata found in webhook")

    try:
        # Python 3.9 compatible if/elif instead of match
        if event_type in (
            "subscription.active",
            "subscription.renewed",
            "subscription.plan_changed",
            "checkout.session.completed",
        ):
            # Identify the user
            meta = data.get("metadata") or {}
            logger.info(f"🔍 Processing {event_type} - metadata: {meta}")

            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")

            logger.info(f"👤 Looking for user - firebase_uid: {firebase_uid}, email: {email}")

            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
                logger.info(f"🔍 User lookup by firebase_uid: {'found' if user else 'not found'}")
            if not user and email:
                user = db.query(User).filter(User.email == email).first()
                logger.info(f"🔍 User lookup by email: {'found' if user else 'not found'}")

            # Determine target plan from metadata
            selected_plan = meta.get("selected_plan")
            billing_cycle = meta.get("billing_cycle")  # "monthly" or "yearly"
            subscription_id = data.get("subscription_id") or data.get("id")

            logger.info(
                f"📋 Plan details - selected_plan: {selected_plan}, billing_cycle: {billing_cycle}, sub_id: {subscription_id}"
            )

            if not user:
                logger.warning("❌ User not found for webhook event; skipping")
            else:
                logger.info(f"✅ Processing webhook for user {user.id} ({user.email})")
                from datetime import datetime, timedelta

                # Persist subscription_id if provided
                if subscription_id and getattr(user, "subscription_id", None) != subscription_id:
                    try:
                        user.subscription_id = subscription_id
                        db.commit()
                        logger.info(
                            f"💾 Persisted subscription_id for user {user.id}: {subscription_id}"
                        )
                    except Exception as e:
                        db.rollback()
                        logger.error(
                            f"❌ Failed to persist subscription_id for user {user.id}: {e}"
                        )

                # Handle all subscription activation events the same way
                if event_type in (
                    "subscription.active",
                    "checkout.session.completed",
                    "subscription.renewed",
                    "subscription.plan_changed",
                ):
                    logger.info(f"🆕 Processing subscription activation for user {user.id}")

                    # Set subscription start date if not already set
                    if not user.subscription_start_date:
                        user.subscription_start_date = datetime.utcnow()
                        user.clients_this_month = 0
                        user.month_reset_date = datetime.utcnow() + timedelta(days=30)
                        logger.info(f"📅 Set subscription_start_date for user {user.id}")

                    # Track billing cycle
                    if billing_cycle and billing_cycle != "unknown":
                        user.billing_cycle = billing_cycle
                        logger.info(f"🔄 Set billing_cycle to {billing_cycle} for user {user.id}")

                    # Set payment date and subscription status
                    user.last_payment_date = datetime.utcnow()
                    user.subscription_status = "active"
                    logger.info(f"✅ Set subscription_status to active for user {user.id}")

                    # Calculate next billing date based on cycle
                    if user.billing_cycle == "yearly":
                        user.next_billing_date = datetime.utcnow() + timedelta(days=365)
                    else:  # monthly or default
                        user.next_billing_date = datetime.utcnow() + timedelta(days=30)

                    # Update plan if provided - this is crucial for immediate access
                    if selected_plan and selected_plan != "unknown":
                        logger.info(
                            f"📋 Updating plan from {user.plan} to {selected_plan} for user {user.id}"
                        )
                        user.plan = selected_plan
                        logger.info(
                            f"✅ User {user.id} plan updated to {selected_plan} via webhook"
                        )
                    else:
                        logger.warning("⚠️ No selected_plan in metadata; plan unchanged")

                    # Commit all changes at once
                    try:
                        # Also persist Dodo customer and default payment method metadata when available
                        customer_obj = (
                            (data.get("customer") or {})
                            if isinstance(data.get("customer"), dict)
                            else {}
                        )
                        dodo_cust_id = (
                            customer_obj.get("id")
                            or data.get("customer_id")
                            or data.get("customerId")
                        )
                        if dodo_cust_id and getattr(user, "dodo_customer_id", None) != dodo_cust_id:
                            user.dodo_customer_id = dodo_cust_id
                            logger.info(
                                f"💾 Stored dodo_customer_id for user {user.id}: {dodo_cust_id}"
                            )

                        pm = (
                            data.get("default_payment_method")
                            or customer_obj.get("default_payment_method")
                            or data.get("payment_method")
                            or {}
                        )
                        if isinstance(pm, dict):
                            card = pm.get("card") or {}
                            pm_id = pm.get("payment_method_id") or pm.get("id")
                            pm_type = pm.get("type") or "card"
                            brand = card.get("brand") or pm.get("brand")
                            last4 = card.get("last4") or pm.get("last4")
                            exp_month = card.get("exp_month") or pm.get("exp_month")
                            exp_year = card.get("exp_year") or pm.get("exp_year")

                            # Only store non-PCI metadata
                            if pm_id or last4 or brand:
                                user.dodo_default_payment_method_id = (
                                    pm_id or user.dodo_default_payment_method_id
                                )
                                user.dodo_payment_method_type = (
                                    pm_type or user.dodo_payment_method_type
                                )
                                user.dodo_payment_method_brand = (
                                    brand or user.dodo_payment_method_brand
                                )
                                user.dodo_payment_method_last4 = (
                                    last4 or user.dodo_payment_method_last4
                                )
                                if exp_month:
                                    user.dodo_payment_method_exp_month = exp_month
                                if exp_year:
                                    user.dodo_payment_method_exp_year = exp_year
                                logger.info(
                                    f"💾 Stored masked payment method for user {user.id}: brand={brand}, last4={last4}"
                                )

                        # Persist billing address if present (non-sensitive PII)
                        billing = data.get("billing") or customer_obj.get("billing") or {}
                        if isinstance(billing, dict):
                            street = billing.get("street")
                            city = billing.get("city")
                            state = billing.get("state")
                            zipcode_val = billing.get("zipcode")
                            zipcode = str(zipcode_val) if zipcode_val is not None else None
                            country = billing.get("country")
                            if street or city or state or zipcode or country:
                                from datetime import datetime

                                user.billing_street = street or user.billing_street
                                user.billing_city = city or user.billing_city
                                user.billing_state = state or user.billing_state
                                user.billing_zipcode = zipcode or user.billing_zipcode
                                user.billing_country = country or user.billing_country
                                user.billing_updated_at = datetime.utcnow()
                                logger.info(f"💾 Stored billing address for user {user.id}")
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed extracting customer/payment method from webhook for user {user.id}: {e}"
                        )

                    try:
                        db.commit()
                        logger.info(
                            f"💾 Successfully committed all subscription changes for user {user.id}"
                        )
                    except Exception as e:
                        db.rollback()
                        logger.error(
                            f"❌ Failed to commit subscription changes for user {user.id}: {e}"
                        )
                        raise

        elif event_type in ("subscription.cancelled", "subscription.canceled"):
            # Cancelled subscription - revoke access
            meta = data.get("metadata") or {}
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")
            subscription_id = data.get("subscription_id") or data.get("id")
            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user:
                user.plan = None
                user.subscription_status = "cancelled"
                user.next_billing_date = None
                # clear stored subscription_id as it's now cancelled
                try:
                    if (
                        subscription_id
                        and getattr(user, "subscription_id", None) == subscription_id
                    ):
                        user.subscription_id = None
                except Exception:
                    pass
                db.commit()
        elif event_type == "invoice.paid":
            # Track successful subscription invoice payment
            meta = data.get("metadata") or {}
            firebase_uid = meta.get("firebase_uid")

            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
                if user:
                    from datetime import datetime

                    user.last_payment_date = datetime.utcnow()
                    user.subscription_status = "active"
                    db.commit()
            logger.info("Invoice paid event processed")

        elif event_type == "payment.succeeded":
            # Handle client invoice payment
            await _handle_client_invoice_payment(data, db)

        elif event_type == "invoice.payment_failed":
            # Handle subscription payment failures
            meta = data.get("metadata") or {}
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")

            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user:
                user.subscription_status = "past_due"
                db.commit()
                logger.warning(
                    f"⚠️ Payment failed for user {user.id}, subscription status: past_due"
                )

            logger.info("Invoice payment failed")

        elif event_type in (
            "payment.failed",
            "checkout.session.failed",
            "subscription.payment_failed",
        ):
            # Handle initial checkout/payment failures (non-invoice paths)
            meta = data.get("metadata") or {}
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")

            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user:
                user.subscription_status = "past_due"
                # Do NOT set or grant plan here; keep existing value
                db.commit()
                logger.warning(
                    f"⚠️ Checkout/payment failed for user {user.id}; keeping plan as {user.plan}"
                )

            logger.info("Payment/checkout failed event processed")
        else:
            logger.info(f"Event {event_type} received and ignored (no handler)")

        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed") from e


async def _handle_client_invoice_payment(data, db: Session):
    """Handle payment webhook for client invoices"""
    from datetime import datetime

    from ..email_service import send_payment_received_notification, send_payment_thank_you_email
    from ..models import BusinessConfig, Client
    from ..models_invoice import Invoice

    meta = data.get("metadata") or {}
    invoice_id = meta.get("invoice_id")

    if not invoice_id:
        logger.info(
            "Payment webhook without invoice_id in metadata - likely a subscription payment"
        )
        return
    try:
        invoice = db.query(Invoice).filter(Invoice.id == int(invoice_id)).first()
        if not invoice:
            logger.warning(f"Invoice {invoice_id} not found for payment webhook")
            return

        if invoice.status == "paid":
            logger.info(f"Invoice {invoice_id} already marked as paid")
            return

        # Get related entities first
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        user = db.query(User).filter(User.id == invoice.user_id).first()

        # Update invoice status
        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow()
        invoice.dodo_payment_id = data.get("payment_id") or data.get("id")

        # Increment unread payments counter for provider
        if user:
            user.unread_payments_count = (user.unread_payments_count or 0) + 1

        db.commit()
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == invoice.user_id).first()
        )

        business_name = business_config.business_name if business_config else "Cleaning Service"

        # Send notification to provider
        if user and user.email and user.notify_payment_received:
            try:
                await send_payment_received_notification(
                    provider_email=user.email,
                    provider_name=user.full_name or "Provider",
                    client_name=client.business_name if client else "Client",
                    invoice_number=invoice.invoice_number,
                    amount=invoice.total_amount,
                    currency=invoice.currency,
                    payment_date=datetime.utcnow().strftime("%B %d, %Y"),
                )
            except Exception as e:
                logger.error(f"Failed to send provider notification: {e}")

        # Send thank you email to client
        if client and client.email:
            try:
                await send_payment_thank_you_email(
                    client_email=client.email,
                    client_name=client.contact_name or client.business_name,
                    business_name=business_name,
                    invoice_number=invoice.invoice_number,
                    amount=invoice.total_amount,
                    currency=invoice.currency,
                )
            except Exception as e:
                logger.error(f"Failed to send client thank you email: {e}")

    except Exception as e:
        logger.error(f"Error processing invoice payment: {e}")
        db.rollback()
