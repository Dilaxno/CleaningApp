"""
Integration Request Routes
Allows users to request new integrations and upvote existing requests
"""

import logging
from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import IntegrationRequest, IntegrationRequestVote, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration-requests", tags=["Integration Requests"])


class IntegrationRequestCreate(BaseModel):
    name: str
    logo_url: str
    integration_type: str  # accounting, crm, payment, scheduling, communication, other
    use_case: str

    @classmethod
    def validate_logo_url(cls, v):
        if len(v) > 2000:
            raise ValueError(
                "Logo URL is too long (max 2000 characters). Please use a direct image URL."
            )
        return v


class IntegrationRequestResponse(BaseModel):
    id: int
    name: str
    logo_url: str
    integration_type: str
    use_case: str
    upvotes: int
    status: str
    has_voted: bool = False
    submitted_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class SubmitStatusResponse(BaseModel):
    can_submit: bool
    days_until_next: Optional[int] = None
    seconds_until_next: Optional[int] = None
    last_submission_date: Optional[datetime] = None


@router.get("/submit-status", response_model=SubmitStatusResponse)
async def get_submit_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Check if user can submit a new integration request"""
    one_month_ago = datetime.utcnow() - relativedelta(months=1)
    recent_request = (
        db.query(IntegrationRequest)
        .filter(
            and_(
                IntegrationRequest.user_id == current_user.id,
                IntegrationRequest.created_at >= one_month_ago,
            )
        )
        .order_by(IntegrationRequest.created_at.desc())
        .first()
    )

    if recent_request:
        next_allowed = recent_request.created_at + relativedelta(months=1)
        time_diff = next_allowed - datetime.utcnow()
        days_until_next = time_diff.days
        seconds_until_next = int(time_diff.total_seconds())
        return SubmitStatusResponse(
            can_submit=False,
            days_until_next=max(1, days_until_next),
            seconds_until_next=max(0, seconds_until_next),
            last_submission_date=recent_request.created_at,
        )

    return SubmitStatusResponse(can_submit=True)


@router.get("", response_model=list[IntegrationRequestResponse])
async def get_integration_requests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all integration requests sorted by upvotes (highest first)"""
    requests = (
        db.query(IntegrationRequest)
        .order_by(IntegrationRequest.upvotes.desc(), IntegrationRequest.created_at.desc())
        .all()
    )

    # Get user's votes
    user_votes = (
        db.query(IntegrationRequestVote.integration_request_id)
        .filter(IntegrationRequestVote.user_id == current_user.id)
        .all()
    )
    voted_ids = {v[0] for v in user_votes}

    result = []
    for req in requests:
        submitter = db.query(User).filter(User.id == req.user_id).first()
        result.append(
            IntegrationRequestResponse(
                id=req.id,
                name=req.name,
                logo_url=req.logo_url,
                integration_type=req.integration_type,
                use_case=req.use_case,
                upvotes=req.upvotes,
                status=req.status,
                has_voted=req.id in voted_ids or req.user_id == current_user.id,
                submitted_by=(
                    submitter.full_name or submitter.email.split("@")[0]
                    if submitter
                    else "Anonymous"
                ),
                created_at=req.created_at,
            )
        )

    return result


@router.post("", response_model=IntegrationRequestResponse)
async def create_integration_request(
    data: IntegrationRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a new integration request (limited to 1 per user per month)"""
    logger.info(f"📥 New integration request from user {current_user.id}: {data.name}")

    # Validate logo URL length
    if len(data.logo_url) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Logo URL is too long (max 2000 characters). Please use a direct image URL, not a search result page.",
        )

    # Check if user has already submitted a request this month
    one_month_ago = datetime.utcnow() - relativedelta(months=1)
    recent_request = (
        db.query(IntegrationRequest)
        .filter(
            and_(
                IntegrationRequest.user_id == current_user.id,
                IntegrationRequest.created_at >= one_month_ago,
            )
        )
        .first()
    )

    if recent_request:
        next_allowed = recent_request.created_at + relativedelta(months=1)
        time_diff = next_allowed - datetime.utcnow()
        seconds_remaining = int(time_diff.total_seconds())

        # Format time remaining
        if seconds_remaining > 86400:  # More than 1 day
            days = seconds_remaining // 86400
            hours = (seconds_remaining % 86400) // 3600
            time_str = f"{days} day(s) and {hours} hour(s)"
        elif seconds_remaining > 3600:  # More than 1 hour
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            time_str = f"{hours} hour(s) and {minutes} minute(s)"
        else:  # Less than 1 hour
            minutes = seconds_remaining // 60
            seconds = seconds_remaining % 60
            time_str = f"{minutes} minute(s) and {seconds} second(s)"

        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Rate limit exceeded. Maximum 1 request per month. Try again in {time_str}.",
                "retry_after": seconds_remaining,
                "limit": 1,
                "window_seconds": 30 * 24 * 3600,  # 30 days
            },
        )

    # Check if similar request already exists (case-insensitive name match)
    existing = (
        db.query(IntegrationRequest)
        .filter(func.lower(IntegrationRequest.name) == func.lower(data.name))
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An integration request for '{data.name}' already exists. Please upvote the existing request instead.",
        )

    # Create the request
    request = IntegrationRequest(
        user_id=current_user.id,
        name=data.name,
        logo_url=data.logo_url,
        integration_type=data.integration_type,
        use_case=data.use_case,
        upvotes=1,  # Submitter's implicit vote
        status="pending",
    )
    db.add(request)
    db.flush()  # Flush to get the request.id before adding vote

    # Add submitter's vote
    vote = IntegrationRequestVote(integration_request_id=request.id, user_id=current_user.id)
    db.add(vote)

    db.commit()
    db.refresh(request)
    return IntegrationRequestResponse(
        id=request.id,
        name=request.name,
        logo_url=request.logo_url,
        integration_type=request.integration_type,
        use_case=request.use_case,
        upvotes=request.upvotes,
        status=request.status,
        has_voted=True,
        submitted_by=current_user.full_name or current_user.email.split("@")[0],
        created_at=request.created_at,
    )


@router.post("/{request_id}/upvote")
async def upvote_integration_request(
    request_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Upvote an integration request"""
    request = db.query(IntegrationRequest).filter(IntegrationRequest.id == request_id).first()

    if not request:
        raise HTTPException(status_code=404, detail="Integration request not found")

    # Check if user already voted
    existing_vote = (
        db.query(IntegrationRequestVote)
        .filter(
            and_(
                IntegrationRequestVote.integration_request_id == request_id,
                IntegrationRequestVote.user_id == current_user.id,
            )
        )
        .first()
    )

    if existing_vote:
        raise HTTPException(status_code=400, detail="You have already voted for this integration")

    # Add vote
    vote = IntegrationRequestVote(integration_request_id=request_id, user_id=current_user.id)
    db.add(vote)

    # Increment upvote count
    request.upvotes += 1

    db.commit()

    logger.info(f"👍 User {current_user.id} upvoted integration request {request_id}")

    return {"message": "Vote recorded", "upvotes": request.upvotes}


@router.delete("/{request_id}/upvote")
async def remove_upvote(
    request_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Remove upvote from an integration request"""
    request = db.query(IntegrationRequest).filter(IntegrationRequest.id == request_id).first()

    if not request:
        raise HTTPException(status_code=404, detail="Integration request not found")

    # Check if user is the submitter (can't remove their implicit vote)
    if request.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove vote from your own submission")

    # Find and remove vote
    existing_vote = (
        db.query(IntegrationRequestVote)
        .filter(
            and_(
                IntegrationRequestVote.integration_request_id == request_id,
                IntegrationRequestVote.user_id == current_user.id,
            )
        )
        .first()
    )

    if not existing_vote:
        raise HTTPException(status_code=400, detail="You haven't voted for this integration")

    db.delete(existing_vote)
    request.upvotes = max(1, request.upvotes - 1)  # Never go below 1

    db.commit()

    logger.info(f"👎 User {current_user.id} removed upvote from integration request {request_id}")

    return {"message": "Vote removed", "upvotes": request.upvotes}
