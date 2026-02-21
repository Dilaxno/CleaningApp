"""
Plan limits and utilities for subscription-based client restrictions.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .models import User

# Plan limits configuration (no free plan - all users must have paid plans)
PLAN_LIMITS = {"team": 50, "enterprise": None}  # None means unlimited


def get_plan_limit(plan: Optional[str]) -> Optional[int]:
    """Get the client limit for a given plan. Returns None for unlimited, 0 for no plan."""
    if not plan:
        return 0  # No plan = no clients allowed
    return PLAN_LIMITS.get(plan.lower(), PLAN_LIMITS["team"])


def _calculate_next_reset_date(subscription_start: datetime, current_time: datetime) -> datetime:
    """
    Calculate the next reset date based on subscription start date.
    Reset happens every 30 days from the subscription start date.
    """
    days_since_start = (current_time - subscription_start).days
    # How many complete 30-day cycles have passed
    cycles_passed = days_since_start // 30
    # Next reset is at the start of the next cycle
    next_reset = subscription_start + timedelta(days=(cycles_passed + 1) * 30)
    return next_reset


def check_and_reset_monthly_counter(user: User, db: Session) -> None:
    """
    Check if the billing period has rolled over and reset the counter if needed.
    Reset happens 30 days after the subscription start date, not on the first of the month.
    """
    now = datetime.utcnow()

    # Use subscription_start_date if available, otherwise fall back to created_at
    subscription_start = user.subscription_start_date or user.created_at or now

    # If no reset date set, initialize it based on subscription start
    if user.month_reset_date is None:
        next_reset = _calculate_next_reset_date(subscription_start, now)
        user.month_reset_date = next_reset
        user.clients_this_month = 0
        db.commit()
        return

    # Check if we've passed the reset date
    if now >= user.month_reset_date:
        # Reset counter
        user.clients_this_month = 0

        # Calculate next reset date (30 days from subscription anniversary)
        next_reset = _calculate_next_reset_date(subscription_start, now)
        user.month_reset_date = next_reset
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
    return (
        False,
        f"You've reached your plan limit of {limit} clients per month. Please upgrade to add more clients.",
    )


def increment_client_count(user: User, db: Session) -> None:
    """
    Increment the user's monthly client count.
    Should be called when a client signs the contract (commits to the service).
    This counts the client for plan limits and statistics.
    """
    check_and_reset_monthly_counter(user, db)
    user.clients_this_month += 1
    db.commit()


def decrement_client_count(user: User, db: Session) -> None:
    """
    Decrement the user's monthly client count.
    Should be called when a client is deleted.
    Only decrements if count is greater than 0.
    """
    check_and_reset_monthly_counter(user, db)
    if user.clients_this_month > 0:
        user.clients_this_month -= 1
        db.commit()


def get_usage_stats(user: User, db: Session) -> dict:
    """
    Get current usage statistics for the user.
    Returns dict with limit, current, remaining, and reset_date.
    Counts clients with 'scheduled' or 'active' status created this month.
    """
    from datetime import datetime
    from ..models import Client

    check_and_reset_monthly_counter(user, db)

    limit = get_plan_limit(user.plan)

    # Count actual clients with scheduled or active status from this month
    # Use subscription_start_date or month_reset_date to determine the billing period
    if user.month_reset_date:
        # Calculate the start of the current billing period
        from dateutil.relativedelta import relativedelta

        billing_start = user.month_reset_date - relativedelta(months=1)
    elif user.subscription_start_date:
        billing_start = user.subscription_start_date
    else:
        # Fallback to start of current calendar month
        now = datetime.utcnow()
        billing_start = datetime(now.year, now.month, 1)

    # Count clients with scheduled or active status created in this billing period
    current = (
        db.query(Client)
        .filter(
            Client.user_id == user.id,
            Client.status.in_(["scheduled", "active"]),
            Client.created_at >= billing_start,
        )
        .count()
    )

    # Update the counter in the database to match actual count
    if user.clients_this_month != current:
        user.clients_this_month = current
        db.commit()

    return {
        "plan": user.plan,
        "limit": limit,  # None for unlimited
        "current": current,
        "remaining": None if limit is None else max(0, limit - current),
        "reset_date": user.month_reset_date.isoformat() if user.month_reset_date else None,
    }
