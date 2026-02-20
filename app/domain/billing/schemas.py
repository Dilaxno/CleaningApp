"""Billing domain schemas - Pydantic models for validation"""

from typing import Optional

from pydantic import BaseModel, field_validator


class CheckoutRequest(BaseModel):
    """Schema for creating a checkout session"""

    product_id: str
    plan: Optional[str] = None  # "team" | "enterprise"
    billing_cycle: Optional[str] = None  # "monthly" | "yearly"
    quantity: int = 1
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
    """Schema for updating user plan"""

    plan: str  # "team", "enterprise"


class CancelRequest(BaseModel):
    """Schema for canceling subscription"""

    cancel_at_period_end: bool = True
    revoke_access_now: bool = False


class ChangePlanRequest(BaseModel):
    """Schema for changing subscription plan"""

    product_id: str
    quantity: int = 1
    proration_billing_mode: str = "prorated_immediately"
    plan: Optional[str] = None


class PaymentMethodResponse(BaseModel):
    """Schema for payment method response"""

    dodo_customer_id: Optional[str] = None
    payment_method: Optional[dict] = None


class PaymentItem(BaseModel):
    """Schema for payment item"""

    id: str
    created_at: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None


class BillingAddressResponse(BaseModel):
    """Schema for billing address response"""

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class PaymentsResponse(BaseModel):
    """Schema for payments list response"""

    payments: list[PaymentItem]


class UsageStatsResponse(BaseModel):
    """Schema for usage statistics response"""

    clients_count: int
    contracts_count: int
    schedules_count: int
    clients_limit: int
    contracts_limit: int
    schedules_limit: int
    plan: Optional[str] = None
    billing_cycle: Optional[str] = None
    subscription_status: Optional[str] = None


class CurrentPlanResponse(BaseModel):
    """Schema for current plan response"""

    plan: Optional[str] = None
    billing_cycle: Optional[str] = None
    subscription_status: Optional[str] = None
    dodo_customer_id: Optional[str] = None
    dodo_subscription_id: Optional[str] = None
