"""
Visit Management Routes
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Contract, User
from ..models_visit import Visit
from ..services.visit_service import VisitService

router = APIRouter(prefix="/visits", tags=["visits"])


# Schemas
class VisitResponse(BaseModel):
    id: int
    public_id: str
    contract_id: int
    client_id: int
    visit_number: int
    title: str
    description: Optional[str]
    scheduled_date: datetime
    scheduled_start_time: Optional[str]
    scheduled_end_time: Optional[str]
    duration_minutes: Optional[int]
    actual_start_time: Optional[datetime]
    actual_end_time: Optional[datetime]
    status: str
    visit_amount: Optional[float]
    currency: str
    payment_method: Optional[str]
    payment_status: Optional[str]
    payment_captured_at: Optional[datetime]
    square_invoice_id: Optional[str]
    square_invoice_url: Optional[str]
    provider_notes: Optional[str]
    client_notes: Optional[str]
    completion_notes: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VisitListResponse(BaseModel):
    upcoming: List[VisitResponse]
    past: List[VisitResponse]
    total_upcoming: int
    total_past: int


class StartVisitRequest(BaseModel):
    notes: Optional[str] = None


class CompleteVisitRequest(BaseModel):
    completion_notes: Optional[str] = None


class GenerateVisitsRequest(BaseModel):
    contract_id: int
    limit: int = 10


# Routes
@router.get("/contract/{contract_id}", response_model=VisitListResponse)
async def get_contract_visits(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all visits for a contract (upcoming and past)"""
    # Verify contract ownership
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Auto-generate more visits if needed
    VisitService.auto_generate_next_visits(db, contract_id)

    # Get visits
    upcoming = VisitService.get_upcoming_visits(db, contract_id, limit=10)
    past = VisitService.get_past_visits(db, contract_id)

    return VisitListResponse(
        upcoming=[VisitResponse.from_orm(v) for v in upcoming],
        past=[VisitResponse.from_orm(v) for v in past],
        total_upcoming=len(upcoming),
        total_past=len(past),
    )


@router.post("/generate", response_model=List[VisitResponse])
async def generate_visits(
    data: GenerateVisitsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate visits for a contract"""
    contract = (
        db.query(Contract)
        .filter(Contract.id == data.contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.status != "active":
        raise HTTPException(status_code=400, detail="Contract must be active to generate visits")

    visits = VisitService.generate_visits_for_contract(db, contract, limit=data.limit)

    return [VisitResponse.from_orm(v) for v in visits]


@router.post("/{visit_id}/start", response_model=VisitResponse)
async def start_visit(
    visit_id: int,
    data: StartVisitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a visit (mark as in progress)"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Verify ownership
    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        if data.notes:
            visit.provider_notes = data.notes
            db.commit()

        updated_visit = VisitService.start_visit(db, visit_id, current_user.firebase_uid)
        return VisitResponse.from_orm(updated_visit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{visit_id}/complete", response_model=VisitResponse)
async def complete_visit(
    visit_id: int,
    data: CompleteVisitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a visit and trigger billing"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Verify ownership
    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        updated_visit = VisitService.complete_visit(
            db, visit_id, current_user.firebase_uid, data.completion_notes
        )

        # Auto-generate next batch of visits
        VisitService.auto_generate_next_visits(db, visit.contract_id)

        return VisitResponse.from_orm(updated_visit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(
    visit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single visit by ID"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Verify ownership
    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return VisitResponse.from_orm(visit)


@router.patch("/{visit_id}/notes")
async def update_visit_notes(
    visit_id: int,
    notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update provider notes for a visit"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    visit.provider_notes = notes
    db.commit()

    return {"message": "Notes updated successfully"}
