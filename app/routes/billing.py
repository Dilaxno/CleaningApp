import logging
import hmac
import hashlib
import json
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
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
if not DODO_PAYMENTS_API_KEY:
    logger.warning("DODO_PAYMENTS_API_KEY not set; billing endpoints will fail until configured")

dodo_client = AsyncDodoPayments(
    bearer_token=DODO_PAYMENTS_API_KEY or "",
    environment=DODO_PAYMENTS_ENVIRONMENT or "test_mode",
)

router = APIRouter(prefix="/billing", tags=["Billing"])
webhooks_router = APIRouter(tags=["Webhooks"])


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
    plan: str  # "free", "solo", "team", "enterprise"


# Plan limits configuration
PLAN_LIMITS = {
    "free": {"clients": 2, "contracts": 5, "schedules": 10},
    "solo": {"clients": 10, "contracts": 25, "schedules": 50},
    "team": {"clients": 50, "contracts": 100, "schedules": 200},
    "enterprise": {"clients": 999999, "contracts": 999999, "schedules": 999999},  # Unlimited
}


@router.get("/usage-stats")
async def get_usage_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get usage statistics for the current billing period (current month)"""
    from datetime import datetime
    from ..models import Client, Contract, Schedule
    
    # Get current month's start and end
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1)
    else:
        month_end = datetime(now.year, now.month + 1, 1)
    
    # Count clients created this month
    clients_count = db.query(Client).filter(
        Client.user_id == user.id,
        Client.created_at >= month_start,
        Client.created_at < month_end
    ).count()
    
    # Count contracts created this month
    contracts_count = db.query(Contract).filter(
        Contract.user_id == user.id,
        Contract.created_at >= month_start,
        Contract.created_at < month_end
    ).count()
    
    # Count schedules this month
    schedules_count = db.query(Schedule).filter(
        Schedule.user_id == user.id,
        Schedule.scheduled_date >= month_start,
        Schedule.scheduled_date < month_end
    ).count()
    
    # Get plan limits
    plan = user.plan or "free"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    
    # Calculate reset date (first of next month)
    if now.month == 12:
        reset_date = datetime(now.year + 1, 1, 1)
    else:
        reset_date = datetime(now.year, now.month + 1, 1)
    
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
    allowed_plans = {"free", "solo", "team", "enterprise"}
    if body.plan not in allowed_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {allowed_plans}")
    
    user.plan = body.plan
    db.commit()
    logger.info(f"User {user.id} plan manually updated to {body.plan}")
    return {"message": f"Plan updated to {body.plan}", "plan": body.plan}


@router.get("/current-plan")
async def get_current_plan(
    user: User = Depends(get_current_user),
):
    """Get the current user's plan"""
    return {"plan": user.plan or "free"}


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
    if not DODO_PAYMENTS_API_KEY:
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
            # subscription_data={"trial_period_days": 7},
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


def _constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def _compute_signature(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


# No product-to-plan mapping on backend; plan is derived from metadata set at checkout creation.


@webhooks_router.post("/webhooks/dodopayments")
async def handle_dodopayments_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Verify signature and process subscription lifecycle events.
    Security per docs:
      - Header: 'webhook-signature' (HMAC-SHA256 of raw body with your webhook secret)
      - Optional headers: 'webhook-id', 'webhook-timestamp' for idempotency/logging
    Docs:
      - https://github.com/dodopayments/dodo-docs/blob/main/developer-resources/fastapi-boilerplate.mdx
      - https://github.com/dodopayments/dodo-docs/blob/main/miscellaneous/faq.mdx
    """
    raw_body = await request.body()
    signature_header = request.headers.get("webhook-signature", "")
    webhook_id = request.headers.get("webhook-id", "")
    webhook_timestamp = request.headers.get("webhook-timestamp", "")

    if not DODO_PAYMENTS_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook not configured")

    computed = _compute_signature(DODO_PAYMENTS_WEBHOOK_SECRET, raw_body)
    if not signature_header or not _constant_time_compare(computed, signature_header):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("type")
    data = event.get("data") or {}
    logger.info(f"Webhook received id={webhook_id} ts={webhook_timestamp} type={event_type}")

    try:
        # Python 3.9 compatible if/elif instead of match
        if event_type in ("subscription.active", "subscription.renewed", "checkout.session.completed"):
            # Identify the user
            meta = (data.get("metadata") or {})
            logger.info(f"Webhook metadata: {meta}")
            logger.info(f"Webhook data: {data}")
            
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")

            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            # Determine target plan from metadata selected_plan
            selected_plan = meta.get("selected_plan")
            logger.info(f"Selected plan from metadata: {selected_plan}, user found: {user is not None}")

            if not user:
                logger.warning("User not found for webhook event; skipping")
            else:
                if selected_plan and selected_plan != "unknown":
                    user.plan = selected_plan
                    db.commit()
                    logger.info(f"User {user.id} plan updated to {selected_plan} via webhook")
                else:
                    logger.info("No selected_plan in metadata; plan unchanged")

        elif event_type in ("subscription.cancelled", "subscription.canceled"):
            # Cancelled subscription moves to 'free'
            meta = (data.get("metadata") or {})
            firebase_uid = meta.get("firebase_uid")
            email = (data.get("customer") or {}).get("email") or data.get("email")
            user: Optional[User] = None
            if firebase_uid:
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
            if not user and email:
                user = db.query(User).filter(User.email == email).first()

            if user:
                user.plan = "free"
                db.commit()
                logger.info(f"User {user.id} plan set to free (cancelled)")

        elif event_type == "invoice.paid":
            # Optional: mark last invoice paid
            logger.info("Invoice paid event processed")

        elif event_type == "invoice.payment_failed":
            logger.info("Invoice payment failed")

        else:
            logger.info(f"Event {event_type} received and ignored (no handler)")

        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")