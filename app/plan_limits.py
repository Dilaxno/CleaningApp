"""
Plan limits and utilities for subscription-based client restrictions.
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from .models import User

# Plan limits configuration (no free plan - all users must have paid plans)
PLAN_LIMITS = {
    "solo": 10,
    "team": 50,
    "enterprise": None  # None means unlimited
}

def get_plan_limit(plan: Optional[str]) -> Optional[int]:
    """Get the client limit for a given plan. Returns None for unlimited, 0 for no plan."""
    if not plan:
        return 0  # No plan = no clients allowed
    return PLAN_LIMITS.get(plan.lower(), PLAN_LIMITS["solo"])

def check_and_reset_monthly_counter(user: User, db: Session) -> None:
    """
    Check if the month has rolled over and reset the counter if needed.
    Sets the month_reset_date to the first day of next month.
    """
    now = datetime.utcnow()
    
    # If no reset date set, initialize it to next month
    if user.month_reset_date is None:
        # Set to first day of next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        user.month_reset_date = next_month
        user.clients_this_month = 0
        db.commit()
        return
    
    # Check if we've passed the reset date
    if now >= user.month_reset_date:
        # Reset counter
        user.clients_this_month = 0
        
        # Set next reset date to first day of next month
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        user.month_reset_date = next_month
        db.commit()

def can_add_client(user: User, db: Session) -> tuple:
    """
    Check if user can add another client this month.
    Returns (can_add, error_message).
    """
    # Check if user has a plan
    if not user.plan:
        return (False, "Please select a plan to start adding clients.")
    
    # Reset counter if needed
    check_and_reset_monthly_counter(user, db)
    
    # Get plan limit
    limit = get_plan_limit(user.plan)
    
    # Unlimited plan
    if limit is None:
        return (True, None)
    
    # Check if under limit
    if user.clients_this_month < limit:
        return (True, None)
    
    # Limit reached
    return (False, f"You've reached your plan limit of {limit} clients per month. Please upgrade to add more clients.")

def increment_client_count(user: User, db: Session) -> None:
    """
    Increment the user's monthly client count.
    Should be called when a contract is fully signed by both parties.
    """
    check_and_reset_monthly_counter(user, db)
    user.clients_this_month += 1
    db.commit()

def get_usage_stats(user: User, db: Session) -> dict:
    """
    Get current usage statistics for the user.
    Returns dict with limit, current, remaining, and reset_date.
    """
    check_and_reset_monthly_counter(user, db)
    
    limit = get_plan_limit(user.plan)
    current = user.clients_this_month
    
    return {
        "plan": user.plan,
        "limit": limit,  # None for unlimited
        "current": current,
        "remaining": None if limit is None else max(0, limit - current),
        "reset_date": user.month_reset_date.isoformat() if user.month_reset_date else None
    }
