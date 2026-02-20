"""Subscription service - Business logic for subscription management"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...config import FRONTEND_URL
from ...models import User
from .dodo_service import dodo_service
from .repository import BillingRepository
from .schemas import CancelRequest, ChangePlanRequest, CheckoutRequest

logger = logging.getLogger(__name__)

# Plan limits configuration
PLAN_LIMITS = {
    "team": {"clients": 50, "contracts": 50, "schedules": 50},
    "enterprise": {"clients": 999999, "contracts": 999999, "schedules": 999999},
}

NO_PLAN_LIMITS = {"clients": 0, "contracts": 0, "schedules": 0}


class SubscriptionService:
    """Service for subscription management"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = BillingRepository()

    def get_plan_limits(self, plan: Optional[str]) -> dict:
        """Get limits for a specific plan"""
        if not plan:
            return NO_PLAN_LIMITS
        return PLAN_LIMITS.get(plan, NO_PLAN_LIMITS)

    def get_usage_stats(self, user: User) -> dict:
        """Get usage statistics for the current billing period"""
        # Calculate billing period start (30 days from subscription date or now)
        now = datetime.utcnow()
        billing_period_start = now - timedelta(days=30)

        # Get usage counts
        usage = self.repo.get_usage_counts(self.db, user.id, billing_period_start)

        # Get plan limits
        limits = self.get_plan_limits(user.plan)

        return {
            "clients_count": usage["clients_count"],
            "contracts_count": usage["contracts_count"],
            "schedules_count": usage["schedules_count"],
            "clients_limit": limits["clients"],
            "contracts_limit": limits["contracts"],
            "schedules_limit": limits["schedules"],
            "plan": user.plan,
            "billing_cycle": user.billing_cycle,
            "subscription_status": user.subscription_status,
        }

    def get_current_plan(self, user: User) -> dict:
        """Get current plan information"""
        return {
            "plan": user.plan,
            "billing_cycle": user.billing_cycle,
            "subscription_status": user.subscription_status,
            "dodo_customer_id": getattr(user, "dodo_customer_id", None),
            "dodo_subscription_id": getattr(user, "subscription_id", None),
        }

    async def create_checkout_session(self, request: CheckoutRequest, user: User) -> dict:
        """Create a checkout session"""
        if not dodo_service.is_available():
            raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

        # Build return URLs
        success_url = f"{FRONTEND_URL}{request.return_path or '/billing?checkout=success'}"
        cancel_url = f"{FRONTEND_URL}/billing?checkout=cancel"

        # Prepare metadata
        metadata = {
            "firebase_uid": user.firebase_uid,
            "user_email": user.email,
        }
        if request.plan:
            metadata["plan"] = request.plan
        if request.billing_cycle:
            metadata["billing_cycle"] = request.billing_cycle

        try:
            response = await dodo_service.create_checkout_session(
                product_id=request.product_id,
                customer_email=user.email,
                success_url=success_url,
                cancel_url=cancel_url,
                quantity=request.quantity,
                metadata=metadata,
            )

            logger.info(f"✅ Created checkout session for user {user.id}: {response.get('id')}")

            return {
                "checkout_url": response.get("url"),
                "session_id": response.get("id"),
            }
        except Exception as e:
            logger.error(f"Failed to create checkout session for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create checkout session")

    async def cancel_subscription(self, request: CancelRequest, user: User) -> dict:
        """Cancel user's subscription"""
        subscription_id = getattr(user, "subscription_id", None)
        if not subscription_id:
            raise HTTPException(status_code=400, detail="No active subscription found")

        if not dodo_service.is_available():
            raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

        try:
            # Cancel subscription in Dodo
            await dodo_service.cancel_subscription(
                subscription_id=subscription_id,
                cancel_at_period_end=request.cancel_at_period_end,
            )

            # Update local status
            if request.revoke_access_now:
                self.repo.update_user_plan(
                    self.db,
                    user,
                    plan=None,
                    subscription_status="canceled",
                )
                message = "Subscription canceled and access revoked immediately"
            elif request.cancel_at_period_end:
                self.repo.update_user_plan(
                    self.db,
                    user,
                    subscription_status="canceling",
                )
                message = "Subscription will be canceled at the end of the billing period"
            else:
                self.repo.update_user_plan(
                    self.db,
                    user,
                    subscription_status="canceled",
                )
                message = "Subscription canceled"

            logger.info(f"✅ Canceled subscription for user {user.id}")

            return {"message": message, "status": user.subscription_status}
        except Exception as e:
            logger.error(f"Failed to cancel subscription for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to cancel subscription")

    async def change_plan(self, request: ChangePlanRequest, user: User) -> dict:
        """Change subscription plan"""
        subscription_id = getattr(user, "subscription_id", None)
        if not subscription_id:
            raise HTTPException(status_code=400, detail="No active subscription found")

        if not dodo_service.is_available():
            raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

        try:
            # Update subscription in Dodo
            response = await dodo_service.update_subscription(
                subscription_id=subscription_id,
                product_id=request.product_id,
                quantity=request.quantity,
                proration_billing_mode=request.proration_billing_mode,
            )

            # Update local plan if provided
            if request.plan:
                self.repo.update_user_plan(self.db, user, plan=request.plan)

            logger.info(f"✅ Changed plan for user {user.id} to {request.product_id}")

            return {
                "message": "Plan changed successfully",
                "subscription": response,
            }
        except Exception as e:
            logger.error(f"Failed to change plan for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to change plan")

    def update_plan_manually(self, user: User, plan: str) -> dict:
        """Manually update user plan (admin function)"""
        if plan not in PLAN_LIMITS:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

        self.repo.update_user_plan(
            self.db,
            user,
            plan=plan,
            subscription_status="active",
        )

        logger.info(f"✅ Manually activated plan {plan} for user {user.id}")

        return {
            "message": f"Plan {plan} activated successfully",
            "plan": user.plan,
            "limits": self.get_plan_limits(plan),
        }

    async def get_payment_method(self, user: User) -> dict:
        """Get user's payment method"""
        dodo_customer_id = getattr(user, "dodo_customer_id", None)
        if not dodo_customer_id:
            return {
                "dodo_customer_id": None,
                "payment_method": None,
            }

        if not dodo_service.is_available():
            raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

        try:
            payment_method = await dodo_service.get_payment_method(dodo_customer_id)
            return {
                "dodo_customer_id": dodo_customer_id,
                "payment_method": payment_method,
            }
        except Exception as e:
            logger.error(f"Failed to get payment method for user {user.id}: {e}")
            return {
                "dodo_customer_id": dodo_customer_id,
                "payment_method": None,
            }

    async def get_payments(self, user: User, limit: int = 10) -> list:
        """Get user's payment history"""
        dodo_customer_id = getattr(user, "dodo_customer_id", None)
        if not dodo_customer_id:
            return []

        if not dodo_service.is_available():
            raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

        try:
            payments = await dodo_service.list_payments(dodo_customer_id, limit)
            return payments
        except Exception as e:
            logger.error(f"Failed to get payments for user {user.id}: {e}")
            return []
