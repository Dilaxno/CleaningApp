"""Billing router - FastAPI endpoints for billing operations"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from .schemas import (
    CancelRequest,
    ChangePlanRequest,
    CheckoutRequest,
    CurrentPlanResponse,
    PaymentMethodResponse,
    PaymentsResponse,
    UpdatePlanRequest,
    UsageStatsResponse,
)
from .subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_subscription_service(db: Session = Depends(get_db)) -> SubscriptionService:
    """Dependency injection for SubscriptionService"""
    return SubscriptionService(db)


# ============================================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================================


@router.get("/usage-stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get usage statistics for the current billing period"""
    return service.get_usage_stats(user)


@router.get("/current-plan", response_model=CurrentPlanResponse)
async def get_current_plan(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get current plan information"""
    return service.get_current_plan(user)


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Create a checkout session"""
    return await service.create_checkout_session(body, user)


@router.post("/cancel")
async def cancel_subscription(
    body: CancelRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Cancel subscription"""
    return await service.cancel_subscription(body, user)


@router.post("/change-plan")
async def change_subscription_plan(
    body: ChangePlanRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Change subscription plan"""
    return await service.change_plan(body, user)


@router.post("/update-plan")
async def update_user_plan(
    body: UpdatePlanRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Manually update user plan (admin function)"""
    return service.update_plan_manually(user, body.plan)


@router.post("/activate-plan")
async def manually_activate_plan(
    request: dict,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Manually activate a plan (admin function)"""
    plan = request.get("plan")
    if not plan:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Plan is required")

    return service.update_plan_manually(user, plan)


# ============================================================================
# PAYMENT INFORMATION
# ============================================================================


@router.get("/payment-method", response_model=PaymentMethodResponse)
async def get_user_payment_method(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get user's payment method"""
    return await service.get_payment_method(user)


@router.get("/payments", response_model=PaymentsResponse)
async def get_user_payments(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get user's payment history"""
    payments = await service.get_payments(user, limit=10)
    return {"payments": payments}


@router.get("/billing-address")
async def get_billing_address(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get billing address (placeholder for future implementation)"""
    # TODO: Implement billing address retrieval from Dodo Payments
    return {
        "street": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
    }


# ============================================================================
# DEBUG ENDPOINTS (kept from original for backward compatibility)
# ============================================================================
# Note: Debug endpoints and webhook handlers are kept in the original
# billing.py file for now to avoid breaking changes.
# These will be refactored in a future phase.

from ...routes.billing import (
    bypass_signature_webhook,
    debug_dodo_webhook,
    debug_find_user,
    debug_user_status,
    download_payment_invoice_pdf,
    handle_dodopayments_webhook,
    manual_fix_from_webhook_logs,
    manual_fix_user_plan,
    test_byte_perfect_signature,
    webhooks_router,
)

__all__ = [
    "router",
    "webhooks_router",
    "get_usage_stats",
    "get_current_plan",
    "create_checkout_session",
    "cancel_subscription",
    "change_subscription_plan",
    "update_user_plan",
    "manually_activate_plan",
    "get_user_payment_method",
    "get_user_payments",
    "get_billing_address",
    # Re-exported from original file
    "download_payment_invoice_pdf",
    "debug_find_user",
    "debug_user_status",
    "handle_dodopayments_webhook",
    "bypass_signature_webhook",
    "test_byte_perfect_signature",
    "debug_dodo_webhook",
    "manual_fix_from_webhook_logs",
    "manual_fix_user_plan",
]
