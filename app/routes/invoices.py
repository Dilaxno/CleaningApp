"""
Invoice Routes for Client Invoicing and Payment System
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import (
    DODO_ADHOC_PRODUCT_ID,
    DODO_PAYMENTS_API_KEY,
    DODO_PAYMENTS_ENVIRONMENT,
    FRONTEND_URL,
)
from ..database import get_db
from ..models import BusinessConfig, Client, Contract, Schedule, User
from ..models_invoice import Invoice
from ..utils.sanitization import sanitize_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class InvoiceCreate(BaseModel):
    client_id: int
    contract_id: Optional[int] = None
    schedule_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    service_type: Optional[str] = None  # one-time, weekly, bi-weekly, monthly
    base_amount: float
    addon_amount: float = 0
    tax_rate: float = 0  # Percentage
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    due_days: int = 15


class InvoiceResponse(BaseModel):
    id: int
    public_id: str  # UUID for public access
    invoice_number: str
    client_id: int
    client_name: str
    client_email: Optional[str]
    contract_id: Optional[int]
    schedule_id: Optional[int]
    title: str
    description: Optional[str]
    service_type: Optional[str]
    base_amount: float
    frequency_discount: float
    addon_amount: float
    tax_amount: float
    total_amount: float
    currency: str
    is_recurring: bool
    recurrence_pattern: Optional[str]
    status: str
    payment_link: Optional[str]
    pdf_url: Optional[str]
    issue_date: datetime
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime


def generate_invoice_number(user_id: int, db: Session) -> str:
    """Generate unique invoice number"""
    year = datetime.now().year
    count = (
        db.query(Invoice)
        .filter(Invoice.user_id == user_id, Invoice.created_at >= datetime(year, 1, 1))
        .count()
        + 1
    )
    return f"INV-{year}-{user_id:04d}-{count:04d}"


def calculate_frequency_discount(
    base_amount: float, frequency: str, business_config: BusinessConfig
) -> float:
    """Calculate discount based on cleaning frequency"""
    if not business_config:
        return 0

    if frequency == "weekly" and business_config.discount_weekly:
        return base_amount * (business_config.discount_weekly / 100)
    elif frequency == "bi-weekly" and business_config.discount_monthly:
        return base_amount * (business_config.discount_monthly / 100 / 2)
    elif frequency == "monthly" and business_config.discount_monthly:
        return base_amount * (business_config.discount_monthly / 100)

    return 0


def get_billing_interval(frequency: str) -> tuple:
    """Get Dodo billing interval from frequency"""
    intervals = {
        "weekly": ("week", 1),
        "bi-weekly": ("week", 2),
        "monthly": ("month", 1),
    }
    return intervals.get(frequency, ("month", 1))


@router.get("", response_model=list[InvoiceResponse])
async def get_invoices(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all invoices for the current user"""
    # Optimized query with JOIN to avoid N+1 problem
    query = (
        db.query(Invoice, Client)
        .join(Client, Invoice.client_id == Client.id)
        .filter(Invoice.user_id == current_user.id)
    )

    if status:
        query = query.filter(Invoice.status == status)

    # Order by created_at descending and execute query
    invoice_client_pairs = query.order_by(Invoice.created_at.desc()).all()

    result = []
    for inv, client in invoice_client_pairs:
        result.append(
            InvoiceResponse(
                id=inv.id,
                public_id=inv.public_id,
                invoice_number=inv.invoice_number,
                client_id=inv.client_id,
                client_name=client.business_name if client else "Unknown",
                client_email=client.email if client else None,
                contract_id=inv.contract_id,
                schedule_id=inv.schedule_id,
                title=inv.title,
                description=inv.description,
                service_type=inv.service_type,
                base_amount=inv.base_amount,
                frequency_discount=inv.frequency_discount,
                addon_amount=inv.addon_amount,
                tax_amount=inv.tax_amount,
                total_amount=inv.total_amount,
                currency=inv.currency,
                is_recurring=inv.is_recurring,
                recurrence_pattern=inv.recurrence_pattern,
                status=inv.status,
                payment_link=inv.dodo_payment_link,
                pdf_url=None,  # TODO: Generate presigned URL
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                paid_at=inv.paid_at,
                created_at=inv.created_at,
            )
        )

    return result


@router.post("", response_model=InvoiceResponse)
async def create_invoice(
    data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new invoice"""
    # Verify client belongs to user
    client = (
        db.query(Client)
        .filter(Client.id == data.client_id, Client.user_id == current_user.id)
        .first()
    )

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get business config for discounts
    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    )

    # Calculate amounts
    frequency_discount = calculate_frequency_discount(
        data.base_amount, data.service_type or "one-time", business_config
    )

    subtotal = data.base_amount - frequency_discount + data.addon_amount
    tax_amount = subtotal * (data.tax_rate / 100) if data.tax_rate > 0 else 0
    total_amount = subtotal + tax_amount

    # Guard against zero or negative totals to prevent $0 PWYW links
    if total_amount is None or total_amount <= 0:
        raise HTTPException(status_code=400, detail="Invoice total must be greater than 0")

    # Generate invoice number
    invoice_number = generate_invoice_number(current_user.id, db)

    # Determine billing interval for recurring
    billing_interval = None
    billing_interval_count = 1
    if data.is_recurring and data.recurrence_pattern:
        billing_interval, billing_interval_count = get_billing_interval(data.recurrence_pattern)

    # Create invoice
    invoice = Invoice(
        user_id=current_user.id,
        client_id=data.client_id,
        contract_id=data.contract_id,
        schedule_id=data.schedule_id,
        invoice_number=invoice_number,
        title=data.title,
        description=data.description,
        service_type=data.service_type,
        base_amount=data.base_amount,
        frequency_discount=frequency_discount,
        addon_amount=data.addon_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        is_recurring=data.is_recurring,
        recurrence_pattern=data.recurrence_pattern,
        billing_interval=billing_interval,
        billing_interval_count=billing_interval_count,
        status="pending",
        due_date=datetime.utcnow() + timedelta(days=data.due_days),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return InvoiceResponse(
        id=invoice.id,
        public_id=invoice.public_id,
        invoice_number=invoice.invoice_number,
        client_id=invoice.client_id,
        client_name=client.business_name,
        client_email=client.email,
        contract_id=invoice.contract_id,
        schedule_id=invoice.schedule_id,
        title=invoice.title,
        description=invoice.description,
        service_type=invoice.service_type,
        base_amount=invoice.base_amount,
        frequency_discount=invoice.frequency_discount,
        addon_amount=invoice.addon_amount,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        is_recurring=invoice.is_recurring,
        recurrence_pattern=invoice.recurrence_pattern,
        status=invoice.status,
        payment_link=invoice.dodo_payment_link,
        pdf_url=None,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
    )


@router.post("/{invoice_id}/generate-payment-link")
async def generate_payment_link(
    invoice_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Generate Dodo Payments checkout link using adhoc product with pay-what-you-want"""
    from dodopayments import AsyncDodoPayments

    logger.info(f"💳 Generating payment link for invoice {invoice_id}")

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Invoice already paid")

    # Guard against zero-amount invoices to avoid $0 PWYW checkouts
    if invoice.total_amount is None or invoice.total_amount <= 0:
        raise HTTPException(
            status_code=400, detail="Invoice amount must be greater than 0 to generate payment link"
        )

    if not DODO_PAYMENTS_API_KEY:
        raise HTTPException(status_code=500, detail="Payment system not configured")

    if not DODO_ADHOC_PRODUCT_ID:
        raise HTTPException(status_code=500, detail="Adhoc product not configured")

    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    )
    business_name = business_config.business_name if business_config else "Cleaning Service"

    # Initialize Dodo client
    dodo_client = AsyncDodoPayments(
        bearer_token=DODO_PAYMENTS_API_KEY,
        environment=DODO_PAYMENTS_ENVIRONMENT or "test_mode",
    )

    try:
        # Use the adhoc product instead of creating a new one
        product_id = DODO_ADHOC_PRODUCT_ID
        # Create checkout session with custom amount using pay-what-you-want
        return_url = f"{FRONTEND_URL}/payment/success/{invoice.id}"

        # For pay-what-you-want products, we can set a custom amount
        session_data = {
            "product_cart": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    # Dynamic amount in lowest currency unit (e.g., cents)
                    "amount": int(round(invoice.total_amount * 100)),
                }
            ],
            "customer": {
                "email": client.email or "",
                "name": client.contact_name or client.business_name or "",
            },
            "metadata": {
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "provider_user_id": str(current_user.id),
                "client_id": str(client.id),
                "business_name": business_name,
                "invoice_title": invoice.title,
                "invoice_description": invoice.description
                or f"Cleaning service from {business_name}",
            },
            "return_url": return_url,
        }

        logger.info(f"Creating checkout session with data: {session_data}")
        session = await dodo_client.checkout_sessions.create(**session_data)

        checkout_url = getattr(session, "checkout_url", None) or session.get("checkout_url")
        session_id = getattr(session, "session_id", None) or session.get("session_id")

        if not checkout_url:
            raise HTTPException(status_code=502, detail="Failed to create payment link")

        # Update invoice with payment info (no longer storing product_id since we use adhoc)
        invoice.dodo_product_id = product_id  # Store adhoc product ID for reference
        invoice.dodo_payment_link = checkout_url
        invoice.status = "sent"

        db.commit()
        return {
            "payment_link": checkout_url,
            "session_id": session_id,
            "product_id": product_id,
            "invoice_id": invoice.id,
            "amount": invoice.total_amount,
            "currency": invoice.currency,
        }

    except Exception as e:
        logger.error(f"❌ Failed to create payment link: {e}")
        raise HTTPException(
            status_code=400, detail=f"Failed to create payment link: {str(e)}"
        ) from e


@router.post("/{invoice_id}/send")
async def send_invoice_to_client(
    invoice_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Send invoice with payment link to client via email"""
    from ..email_service import send_invoice_payment_link_email

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    if not client or not client.email:
        raise HTTPException(status_code=400, detail="Client email not found")

    # Generate payment link if not exists
    if not invoice.dodo_payment_link:
        # Call generate payment link first
        await generate_payment_link(invoice_id, current_user, db)
        db.refresh(invoice)

    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    )
    business_name = business_config.business_name if business_config else "Cleaning Service"

    try:
        await send_invoice_payment_link_email(
            to=client.email,
            client_name=sanitize_string(client.contact_name or client.business_name),
            business_name=sanitize_string(business_name),
            invoice_number=sanitize_string(invoice.invoice_number),
            invoice_title=sanitize_string(invoice.title),
            total_amount=invoice.total_amount,
            currency=invoice.currency,
            due_date=invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else None,
            payment_link=invoice.dodo_payment_link,
            is_recurring=invoice.is_recurring,
            recurrence_pattern=(
                sanitize_string(invoice.recurrence_pattern) if invoice.recurrence_pattern else None
            ),
        )

        invoice.status = "sent"
        db.commit()
        return {"message": "Invoice sent successfully", "email": client.email}

    except Exception as e:
        logger.error(f"❌ Failed to send invoice email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}") from e


@router.get("/public/{public_id}")
async def get_public_invoice(public_id: str, db: Session = Depends(get_db)):
    """Public endpoint for client to view invoice using secure UUID (no auth required)"""
    # Validate UUID format to prevent injection
    if not validate_uuid(public_id):
        raise HTTPException(status_code=400, detail="Invalid invoice identifier")

    invoice = db.query(Invoice).filter(Invoice.public_id == public_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    # User data available for future invoice customization
    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == invoice.user_id).first()
    )

    return {
        "id": invoice.id,
        "public_id": invoice.public_id,
        "invoice_number": invoice.invoice_number,
        "title": invoice.title,
        "description": invoice.description,
        "business_name": business_config.business_name if business_config else "Cleaning Service",
        "business_logo": business_config.logo_url if business_config else None,
        "client_name": client.contact_name or client.business_name if client else "Client",
        "client_email": client.email if client else None,
        "service_type": invoice.service_type,
        "base_amount": invoice.base_amount,
        "frequency_discount": invoice.frequency_discount,
        "addon_amount": invoice.addon_amount,
        "tax_amount": invoice.tax_amount,
        "total_amount": invoice.total_amount,
        "currency": invoice.currency,
        "is_recurring": invoice.is_recurring,
        "recurrence_pattern": invoice.recurrence_pattern,
        "status": invoice.status,
        "payment_link": invoice.dodo_payment_link,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
    }


def calculate_addon_amount_from_contract(
    contract: Contract, business_config: BusinessConfig
) -> float:
    """Calculate addon amount from contract's client form data"""
    if not contract or not contract.client or not contract.client.form_data:
        return 0.0

    form_data = contract.client.form_data
    selected_addons = form_data.get("selectedAddons", [])
    addon_quantities = form_data.get("addonQuantities", {})

    if not selected_addons:
        return 0.0

    addon_total = 0.0

    # Process standard add-ons
    if "addon_windows" in selected_addons and business_config.addon_windows:
        quantity = addon_quantities.get("addon_windows", 1)
        addon_total += business_config.addon_windows * quantity

    # Size-based carpet cleaning addons
    if "addon_carpet_small" in selected_addons and business_config.addon_carpet_small:
        quantity = addon_quantities.get("addon_carpet_small", 1)
        addon_total += business_config.addon_carpet_small * quantity

    if "addon_carpet_medium" in selected_addons and business_config.addon_carpet_medium:
        quantity = addon_quantities.get("addon_carpet_medium", 1)
        addon_total += business_config.addon_carpet_medium * quantity

    if "addon_carpet_large" in selected_addons and business_config.addon_carpet_large:
        quantity = addon_quantities.get("addon_carpet_large", 1)
        addon_total += business_config.addon_carpet_large * quantity

    # Legacy carpet addon for backward compatibility
    if "addon_carpets" in selected_addons and business_config.addon_carpets:
        quantity = addon_quantities.get("addon_carpets", 1)
        addon_total += business_config.addon_carpets * quantity

    # Process custom add-ons
    if business_config.custom_addons:
        for custom_addon in business_config.custom_addons:
            addon_id = custom_addon.get("id") or f"custom_{custom_addon.get('name', '')}"
            if addon_id in selected_addons:
                unit_price = float(custom_addon.get("price", 0))
                pricing_metric = custom_addon.get("pricingMetric", "per service")

                # For "per service" or "flat rate", quantity is always 1
                if pricing_metric in ["per service", "flat rate"]:
                    quantity = 1
                else:
                    quantity = addon_quantities.get(addon_id, 1)

                addon_total += unit_price * quantity

    return addon_total


@router.post("/auto-create-from-schedule/{schedule_id}")
async def auto_create_invoice_from_schedule(
    schedule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Automatically create invoice when schedule is confirmed"""
    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id, Schedule.user_id == current_user.id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    client = db.query(Client).filter(Client.id == schedule.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Idempotency: if an invoice already exists for this schedule, return it
    existing_invoice = (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.id, Invoice.schedule_id == schedule.id)
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if existing_invoice:
        return {
            "invoice_id": existing_invoice.id,
            "invoice_number": existing_invoice.invoice_number,
            "total_amount": existing_invoice.total_amount,
            "status": existing_invoice.status,
        }

    # Get contract for pricing info
    contract = (
        db.query(Contract)
        .filter(Contract.client_id == client.id, Contract.user_id == current_user.id)
        .order_by(Contract.created_at.desc())
        .first()
    )

    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    )

    # Determine base amount from contract or schedule
    base_amount = schedule.price or (contract.total_value if contract else 0)

    if base_amount <= 0:
        raise HTTPException(status_code=400, detail="Cannot create invoice with zero amount")

    # Determine service type from client frequency
    service_type = client.frequency or "one-time"
    one_time_frequencies = [
        "one-time",
        "One-time",
        "One-time deep clean",
        "Per turnover",
        "On-demand",
        "As needed",
    ]
    is_recurring = service_type not in one_time_frequencies

    # Calculate addon amount from contract
    addon_amount = 0.0
    if contract and business_config:
        addon_amount = calculate_addon_amount_from_contract(contract, business_config)
    # Calculate frequency discount
    frequency_discount = calculate_frequency_discount(base_amount, service_type, business_config)
    total_amount = base_amount - frequency_discount + addon_amount

    # Generate invoice number
    invoice_number = generate_invoice_number(current_user.id, db)

    # Determine billing interval
    billing_interval = None
    billing_interval_count = 1
    if is_recurring:
        billing_interval, billing_interval_count = get_billing_interval(service_type)

    # Create invoice
    invoice = Invoice(
        user_id=current_user.id,
        client_id=client.id,
        contract_id=contract.id if contract else None,
        schedule_id=schedule.id,
        invoice_number=invoice_number,
        title=f"Cleaning Service - {schedule.title}",
        description=f"Service scheduled for {schedule.scheduled_date.strftime('%B %d, %Y')}",
        service_type=service_type,
        base_amount=base_amount,
        frequency_discount=frequency_discount,
        addon_amount=addon_amount,
        tax_amount=0,
        total_amount=total_amount,
        is_recurring=is_recurring,
        recurrence_pattern=service_type if is_recurring else None,
        billing_interval=billing_interval,
        billing_interval_count=billing_interval_count,
        status="pending",
        due_date=datetime.utcnow()
        + timedelta(days=business_config.payment_due_days if business_config else 15),
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
    }


@router.post("/{invoice_id}/mark-paid")
async def mark_invoice_as_paid(
    invoice_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Manually mark an invoice as paid (for offline payments, cash, check, etc.)
    This endpoint allows providers to mark invoices as paid when payment is received outside the platform
    """
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "paid":
        logger.info(f"Invoice {invoice_id} already marked as paid")
        return {
            "message": "Invoice already marked as paid",
            "invoice_id": invoice.id,
            "status": invoice.status,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        }

    # Update invoice status
    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()
    invoice.dodo_payment_id = f"manual-{datetime.utcnow().timestamp()}"  # Mark as manual payment

    db.commit()
    db.refresh(invoice)
    # Optionally send notification to provider
    from ..email_service import send_payment_received_notification

    client = db.query(Client).filter(Client.id == invoice.client_id).first()

    if current_user.email and current_user.notify_payment_received:
        try:
            await send_payment_received_notification(
                provider_email=current_user.email,
                provider_name=current_user.full_name or "Provider",
                client_name=client.business_name if client else "Client",
                invoice_number=invoice.invoice_number,
                amount=invoice.total_amount,
                currency=invoice.currency,
                payment_date=invoice.paid_at.strftime("%B %d, %Y") if invoice.paid_at else None,
            )
        except Exception as e:
            logger.warning(f"Failed to send payment notification: {e}")

    return {
        "message": "Invoice marked as paid successfully",
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "total_amount": invoice.total_amount,
    }
