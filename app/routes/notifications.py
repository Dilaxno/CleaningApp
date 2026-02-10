from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime
from ..database import get_db
from ..models import User
from ..models_invoice import Invoice
from ..auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationPreferences(BaseModel):
    notify_new_clients: bool
    notify_contract_signed: bool
    notify_schedule_confirmed: bool
    notify_payment_received: bool
    notify_reminders: bool
    notify_marketing: bool

class PaymentNotificationResponse(BaseModel):
    unread_count: int
    recent_payments: list

@router.get("/payment-notifications", response_model=PaymentNotificationResponse)
async def get_payment_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread payment notifications count and recent payments"""
    user = current_user
    # Get recent payments since last check
    last_check = user.last_payment_check or datetime(2020, 1, 1)  # Default to old date if never checked
    
    recent_payments_query = db.query(Invoice).filter(
        Invoice.user_id == user.id,
        Invoice.status == "paid",
        Invoice.paid_at > last_check
    ).order_by(Invoice.paid_at.desc()).limit(10)
    
    recent_payments = []
    for invoice in recent_payments_query:
        recent_payments.append({
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": invoice.total_amount,
            "currency": invoice.currency,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            "client_name": invoice.client.business_name or invoice.client.contact_name if invoice.client else "Unknown"
        })
    
    return PaymentNotificationResponse(
        unread_count=user.unread_payments_count,
        recent_payments=recent_payments
    )

@router.post("/mark-payments-read")
async def mark_payments_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark payment notifications as read"""
    user = current_user
    user.unread_payments_count = 0
    user.last_payment_check = datetime.utcnow()
    db.commit()
    
    return {"message": "Payment notifications marked as read"}

@router.get("/preferences")
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's notification preferences"""
    user = current_user
    return {
        "notify_new_clients": user.notify_new_clients if hasattr(user, 'notify_new_clients') else True,
        "notify_contract_signed": user.notify_contract_signed if hasattr(user, 'notify_contract_signed') else True,
        "notify_schedule_confirmed": user.notify_schedule_confirmed if hasattr(user, 'notify_schedule_confirmed') else True,
        "notify_payment_received": user.notify_payment_received if hasattr(user, 'notify_payment_received') else True,
        "notify_reminders": user.notify_reminders if hasattr(user, 'notify_reminders') else True,
        "notify_marketing": user.notify_marketing if hasattr(user, 'notify_marketing') else False,
    }

@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's notification preferences"""
    user = current_user
    # Update preferences
    user.notify_new_clients = preferences.notify_new_clients
    user.notify_contract_signed = preferences.notify_contract_signed
    user.notify_schedule_confirmed = preferences.notify_schedule_confirmed
    user.notify_payment_received = preferences.notify_payment_received
    user.notify_reminders = preferences.notify_reminders
    user.notify_marketing = preferences.notify_marketing
    
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Notification preferences updated successfully",
        "preferences": {
            "notify_new_clients": user.notify_new_clients,
            "notify_contract_signed": user.notify_contract_signed,
            "notify_schedule_confirmed": user.notify_schedule_confirmed,
            "notify_payment_received": user.notify_payment_received,
            "notify_reminders": user.notify_reminders,
            "notify_marketing": user.notify_marketing,
        }
    }
