from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from ..models import User
from ..auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationPreferences(BaseModel):
    notify_new_clients: bool
    notify_contract_signed: bool
    notify_schedule_confirmed: bool
    notify_payment_received: bool
    notify_reminders: bool
    notify_marketing: bool


@router.get("/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's notification preferences"""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's notification preferences"""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
