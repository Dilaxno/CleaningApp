"""Dodo Payments service - Integration with Dodo Payments API"""

import logging
from typing import Optional

from dodopayments import AsyncDodoPayments  # type: ignore

from ...config import DODO_PAYMENTS_API_KEY, DODO_PAYMENTS_ENVIRONMENT

logger = logging.getLogger(__name__)


def normalize_dodo_environment(env: Optional[str]) -> str:
    """Normalize Dodo environment value to expected format"""
    value = (env or "test_mode").strip().lower()
    if value in {"live", "production", "prod"}:
        return "live_mode"
    if value in {"test", "sandbox", "staging", "dev", "development"}:
        return "test_mode"
    if value in {"test_mode", "live_mode"}:
        return value
    logger.warning(f"Unknown DODO environment '{env}', defaulting to test_mode")
    return "test_mode"


class DodoPaymentsService:
    """Service for Dodo Payments API operations"""

    def __init__(self):
        self.api_key = DODO_PAYMENTS_API_KEY
        self.environment = normalize_dodo_environment(DODO_PAYMENTS_ENVIRONMENT)
        self.client = None

        if not self.api_key:
            logger.warning(
                "DODO_PAYMENTS_API_KEY not set; billing endpoints will fail until configured"
            )
        else:
            try:
                self.client = AsyncDodoPayments(
                    bearer_token=self.api_key,
                    environment=self.environment,
                )
                logger.info(f"Dodo Payments client initialized (env={self.environment})")
            except Exception as e:
                logger.error(f"Failed to initialize Dodo client (env={self.environment}): {e}")
                self.client = None

    def is_available(self) -> bool:
        """Check if Dodo Payments client is available"""
        return self.client is not None

    async def create_checkout_session(
        self,
        product_id: str,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        quantity: int = 1,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create a checkout session with CleanEnroll branding"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.checkout_sessions.create(
                product_cart=[{"product_id": product_id, "quantity": quantity}],
                customer={"email": customer_email},
                return_url=success_url,
                metadata=metadata or {},
                customization={
                    "theme_config": {
                        # Typography / shape
                        "font_primary_url": "https://fonts.googleapis.com/css2?family=Satoshi:wght@400;500;600&display=swap",
                        "font_size": "md",
                        "font_weight": "medium",
                        "radius": "8px",
                        "pay_button_text": "Complete Purchase",
                        # Light mode - CleanEnroll brand colors
                        "light": {
                            "bg_primary": "#ffffff",
                            "bg_secondary": "#f8fafc",
                            "text_primary": "#0f172a",
                            "text_secondary": "#64748b",
                            "text_placeholder": "#94a3b8",
                            "text_error": "#ef4444",
                            "text_success": "#14b8a6",
                            "border_primary": "#e2e8f0",
                            "border_secondary": "#cbd5e1",
                            "button_primary": "#14b8a6",
                            "button_primary_hover": "#0d9488",
                            "button_secondary": "#f1f5f9",
                            "button_secondary_hover": "#e2e8f0",
                            "button_text_primary": "#ffffff",
                            "button_text_secondary": "#334155",
                            "input_focus_border": "#14b8a6",
                        },
                        # Dark mode - CleanEnroll dark theme
                        "dark": {
                            "bg_primary": "#0f172a",
                            "bg_secondary": "#1e293b",
                            "text_primary": "#f8fafc",
                            "text_secondary": "#94a3b8",
                            "text_placeholder": "#64748b",
                            "text_error": "#f87171",
                            "text_success": "#5eead4",
                            "border_primary": "#334155",
                            "border_secondary": "#475569",
                            "button_primary": "#14b8a6",
                            "button_primary_hover": "#2dd4bf",
                            "button_secondary": "#334155",
                            "button_secondary_hover": "#475569",
                            "button_text_primary": "#ffffff",
                            "button_text_secondary": "#e2e8f0",
                            "input_focus_border": "#2dd4bf",
                        },
                    }
                },
            )
            return response
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    async def get_customer(self, customer_id: str) -> dict:
        """Get customer details"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.customers.retrieve(customer_id=customer_id)
            return response
        except Exception as e:
            logger.error(f"Failed to get customer {customer_id}: {e}")
            raise

    async def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.subscriptions.retrieve(subscription_id=subscription_id)
            return response
        except Exception as e:
            logger.error(f"Failed to get subscription {subscription_id}: {e}")
            raise

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> dict:
        """Cancel a subscription"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.subscriptions.cancel(
                subscription_id=subscription_id,
                cancel_at_period_end=cancel_at_period_end,
            )
            return response
        except Exception as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise

    async def update_subscription(
        self,
        subscription_id: str,
        product_id: str,
        quantity: int = 1,
        proration_billing_mode: str = "prorated_immediately",
    ) -> dict:
        """Update a subscription (change plan)"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.subscriptions.update(
                subscription_id=subscription_id,
                product_id=product_id,
                quantity=quantity,
                proration_billing_mode=proration_billing_mode,
            )
            return response
        except Exception as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            raise

    async def list_payments(self, customer_id: str, limit: int = 10) -> list:
        """List payments for a customer"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            response = await self.client.payments.list(customer_id=customer_id, limit=limit)
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Failed to list payments for customer {customer_id}: {e}")
            raise

    async def get_payment_method(self, customer_id: str) -> Optional[dict]:
        """Get payment method for a customer"""
        if not self.client:
            raise Exception("Dodo Payments client not initialized")

        try:
            customer = await self.get_customer(customer_id)
            return customer.get("payment_method")
        except Exception as e:
            logger.error(f"Failed to get payment method for customer {customer_id}: {e}")
            return None


# Singleton instance
dodo_service = DodoPaymentsService()
