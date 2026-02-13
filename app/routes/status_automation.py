"""
API endpoint for status automation and analytics
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Contract, User
from ..services.status_automation import update_contract_statuses

router = APIRouter(prefix="/status", tags=["status"])


class StatusSummary(BaseModel):
    new: int
    signed: int
    scheduled: int
    active: int
    cancelled: int
    completed: int


class AutomationResult(BaseModel):
    scheduled_to_active: int
    active_to_completed: int
    total_updated: int


@router.get("/analytics", response_model=StatusSummary)
async def get_status_analytics(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get count of contracts by status for current user"""

    # Query contract counts by status
    status_counts = (
        db.query(Contract.status, func.count(Contract.id).label("count"))
        .filter(Contract.user_id == current_user.id)
        .group_by(Contract.status)
        .all()
    )

    # Initialize with zeros
    summary = {"new": 0, "signed": 0, "scheduled": 0, "active": 0, "cancelled": 0, "completed": 0}

    # Fill in actual counts
    for status, count in status_counts:
        if status in summary:
            summary[status] = count

    return StatusSummary(**summary)


@router.post("/automation/run", response_model=AutomationResult)
async def run_status_automation(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Manually trigger status automation
    (In production, this should be run via scheduled job/cron)
    """
    result = update_contract_statuses(db)
    return AutomationResult(**result)
