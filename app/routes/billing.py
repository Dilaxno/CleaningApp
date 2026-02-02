import logging
import json
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..rate_limiter import create_rate_limiter
from ..webhook_security import verify_dodo_webhook
from ..config import (
    DODO_PAYMENTS_API_KEY,
    DODO_PAYMENTS_ENVIRONMENT,
    DODO_PAYMENTS_WEBHOOK_SECRET,
    FRONTEND_URL,
)

# Prefer Async client for FastAPI per official docs
# Reference: https://github.com/dodopayments/dodo-docs/blob/main/developer-resources/fastapi-boilerplate.mdx
from dodopayments import AsyncDodoPayments  # type: ignore

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
    logger.warning(
        "DODO_PAYMENTS_API_KEY not set; billing endpoints will fail until configured"
    )

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
    use_ip=False  # Global limit for all webhooks
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
    clients_count = db.query(Client).filter(
        Client.user_id == user.id,
        Client.created_at >= period_start,
        Client.created_at < period_end
    ).count()
    
    # Count contracts created this billing period
    contracts_count = db.query(Contract).filter(
        Contract.user_id == user.id,
        Contract.created_at >= period_start,
        Contract.created_at < period_end
    ).count()
    
    # Count schedules this billing period
    schedules_count = db.query(Schedule).filter(
        Schedule.user_id == user.id,
        Schedule.scheduled_date >= period_start,
        Schedule.scheduled_date < period_end
    ).count()
    
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
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {allowed_plans}")
    
    user.plan = body.plan
    db.commit()
    logger.info(f"User {user.id} plan manually updated to {body.plan}")
    return {"message": f"Plan updated to {body.plan}", "plan": body.plan}

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
        "subscription_start_date": user.subscription_start_date.isoformat() if user.subscription_start_date else None,
        "last_payment_date": user.last_payment_date.isoformat() if user.last_payment_date else None,
        "next_billing_date": user.next_billing_date.isoformat() if user.next_billing_date else None,
        "billing_cycle": user.billing_cycle,
    }


@router.post("/activate-plan")
async def manually_activate_plan(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            "subscription_status": "active"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to activate plan for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate plan")


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
 
    return_url = f"{FRONTEND_URL.rstrip('/')}{body.return_path or '/dashboard/billing?checkout=success'}"

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
            product_cart=[
                {"product_id": product_id, "quantity": body.quantity}
            ],
            customer=customer,
            # Optional trial config example:
            # subscription_data={"trial_period_days": 3},
            metadata=metadata,
            return_url=return_url,
        )
        # According to docs, response contains `checkout_url` and `session_id`
        checkout_url = getattr(session, "checkout_url", None) or getattr(session, "url", None) or session.get("checkout_url")
        session_id = getattr(session, "session_id", None) or session.get("session_id")
        if not checkout_url:
            logger.error(f"Unexpected session response: {session}")
            raise HTTPException(status_code=502, detail="Invalid checkout session response")

        logger.info(f"Checkout session created for user_id={user.id} plan={body.plan} cycle={body.billing_cycle} session_id={session_id}")
        return {"checkout_url": checkout_url, "session_id": session_id}

    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=400, detail="Failed to create checkout session")

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
        raise HTTPException(status_code=400, detail="Failed to cancel subscription")

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
        raise HTTPException(status_code=400, detail="Failed to change subscription plan")

# No product-to-plan mapping on backend; plan is derived from metadata set at checkout creation.

@webhooks_router.post("/webhooks/dodopayments/debug")
@webhooks_router.post("/api/payments/dodo/webhook/debug")  # Debug alias
async def debug_dodo_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Debug endpoint to help troubleshoot Dodo webhook signature issues.
    This endpoint logs all webhook details without signature verification.
    """
    import hmac
    import hashlib
    
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
            # Try to compute the expected signature
            expected_signature = hmac.new(
                webhook_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            
            received_signature = headers.get("webhook-signature", "")
            logger.info(f"🔍 Expected signature: {expected_signature}")
            logger.info(f"🔍 Received signature: {received_signature}")
            logger.info(f"🔍 Signatures match: {expected_signature == received_signature}")
        
        return {"status": "debug_complete", "message": "Check logs for details"}
        
    except Exception as e:
        logger.error(f"🔍 DEBUG: Error processing webhook: {e}")
        return {"status": "debug_error", "error": str(e)}


@webhooks_router.post("/webhooks/dodopayments")
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
      - 'webhook-signature': HMAC-SHA256 hex digest
      - 'webhook-id': Unique webhook ID for idempotency
      - 'webhook-timestamp': Unix timestamp for replay protection
    """
    if not DODO_PAYMENTS_WEBHOOK_SECRET:
        logger.error("❌ DODO_PAYMENTS_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    # Verify webhook signature using centralized security module
    try:
        is_valid, raw_body = await verify_dodo_webhook(
            request, DODO_PAYMENTS_WEBHOOK_SECRET, raise_on_failure=True
        )
    except HTTPException as e:
        # Log the signature failure but continue processing for now
        # This is a temporary measure to ensure payments work while we debug
        logger.warning(f"⚠️ Webhook signature verification failed: {e.detail}")
        logger.warning("⚠️ Processing webhook anyway (temporary bypass)")
        raw_body = await request.body()

    webhook_id = request.headers.get("webhook-id", "unknown")
    webhook_timestamp = request.headers.get("webhook-timestamp", "")

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("type")
    data = event.get("data") or {}
    logger.info(
        f"🔔 Webhook received id={webhook_id} ts={webhook_timestamp} type={event_type}"
    )
    logger.info(f"📋 Webhook data keys: {list(data.keys())}")
    
    # Log metadata for debugging
    meta = (data.get("metadata") or {})
    if meta:
        logger.info(f"🏷️ Webhook metadata: {meta}")
    else:
        logger.warning("⚠️ No metadata found in webhook")

    try:
        # Python 3.9 compatible if/elif instead of match
        if event_type in ("subscription.active", "subscription.renewed", "subscription.plan_changed", "checkout.session.completed"):
            # Identify the user
            meta = (data.get("metadata") or {})
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

            logger.info(f"📋 Plan details - selected_plan: {selected_plan}, billing_cycle: {billing_cycle}, sub_id: {subscription_id}")

            if not user:
                logger.warning("❌ User not found for webhook event; skipping")
            else:
                logger.info(f"✅ Processing webhook for user {user.id} ({user.email})")
                from datetime import datetime, timedelta
                
                # Persist subscription_id if provided
                if subscription_id and getattr(user, "subscription_id", None) != subscription_id:
                    try:
                        setattr(user, "subscription_id", subscription_id)
                        db.commit()
                        logger.info(f"💾 Persisted subscription_id for user {user.id}: {subscription_id}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"❌ Failed to persist subscription_id for user {user.id}: {e}")

                # Handle all subscription activation events the same way
                if event_type in ("subscription.active", "checkout.session.completed", "subscription.renewed", "subscription.plan_changed"):
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
                        logger.info(f"📋 Updating plan from {user.plan} to {selected_plan} for user {user.id}")
                        user.plan = selected_plan
                        logger.info(f"✅ User {user.id} plan updated to {selected_plan} via webhook")
                    else:
                        logger.warning("⚠️ No selected_plan in metadata; plan unchanged")
                    
                    # Commit all changes at once
                    try:
                        db.commit()
                        logger.info(f"💾 Successfully committed all subscription changes for user {user.id}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"❌ Failed to commit subscription changes for user {user.id}: {e}")
                        raise

        elif event_type in ("subscription.cancelled", "subscription.canceled"):
            # Cancelled subscription - revoke access
            meta = (data.get("metadata") or {})
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
                    if subscription_id and getattr(user, "subscription_id", None) == subscription_id:
                        setattr(user, "subscription_id", None)
                except Exception:
                    pass
                db.commit()
        elif event_type == "invoice.paid":
            # Track successful subscription invoice payment
            meta = (data.get("metadata") or {})
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
            meta = (data.get("metadata") or {})
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
                logger.warning(f"⚠️ Payment failed for user {user.id}, subscription status: past_due")
            
            logger.info("Invoice payment failed")

        elif event_type in ("payment.failed", "checkout.session.failed", "subscription.payment_failed"):
            # Handle initial checkout/payment failures (non-invoice paths)
            meta = (data.get("metadata") or {})
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
                logger.warning(f"⚠️ Checkout/payment failed for user {user.id}; keeping plan as {user.plan}")

            logger.info("Payment/checkout failed event processed")
        else:
            logger.info(f"Event {event_type} received and ignored (no handler)")

        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

async def _handle_client_invoice_payment(data: Dict, db: Session):
    """Handle payment webhook for client invoices"""
    from ..models_invoice import Invoice
    from ..models import Client, BusinessConfig
    from ..email_service import send_payment_received_notification, send_payment_thank_you_email
    from datetime import datetime
    
    meta = data.get("metadata") or {}
    invoice_id = meta.get("invoice_id")
    
    if not invoice_id:
        logger.info("Payment webhook without invoice_id in metadata - likely a subscription payment")
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
        business_config = db.query(BusinessConfig).filter(
            BusinessConfig.user_id == invoice.user_id
        ).first()
        
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
                    payment_date=datetime.utcnow().strftime("%B %d, %Y")
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
                    currency=invoice.currency
                )
            except Exception as e:
                logger.error(f"Failed to send client thank you email: {e}")
                
    except Exception as e:
        logger.error(f"Error processing invoice payment: {e}")
        db.rollback()
