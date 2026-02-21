"""
Visit Management Routes
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field, validator
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
    photo_proof_urls: Optional[List[str]]
    photo_count: int
    photos_uploaded_at: Optional[datetime]
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
    photo_urls: List[str] = Field(..., min_items=2, max_items=10)

    @validator("photo_urls")
    def validate_photo_urls(cls, v):
        if len(v) < 2:
            raise ValueError("Minimum 2 photos required")
        if len(v) > 10:
            raise ValueError("Maximum 10 photos allowed")
        return v


class GenerateVisitsRequest(BaseModel):
    contract_id: int
    limit: int = 10


class VisitFilterParams(BaseModel):
    client_id: Optional[int] = None
    contract_id: Optional[int] = None
    status: Optional[str] = None
    month: Optional[int] = None  # 1-12
    year: Optional[int] = None
    week: Optional[int] = None  # ISO week number


class PhotoUploadResponse(BaseModel):
    url: str
    key: str
    uploaded_at: datetime


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
    """Complete a visit with photo proof (min 2, max 10 photos required)"""
    import logging

    logger = logging.getLogger(__name__)

    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Verify ownership
    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate photo requirements
    if not data.photo_urls or len(data.photo_urls) < 2:
        raise HTTPException(status_code=400, detail="Minimum 2 photos required to complete visit")

    if len(data.photo_urls) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 photos allowed")

    # Verify photos match what's uploaded
    if visit.photo_count < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Only {visit.photo_count} photo(s) uploaded. Minimum 2 required.",
        )

    try:
        # Update photo URLs if provided
        if data.photo_urls:
            visit.photo_proof_urls = data.photo_urls
            visit.photo_count = len(data.photo_urls)

        updated_visit = VisitService.complete_visit(
            db, visit_id, current_user.firebase_uid, data.completion_notes
        )

        logger.info(
            f"✅ Visit {visit_id} completed with {visit.photo_count} photos by {current_user.email}"
        )

        # Check if all visits in contract are completed
        contract = db.query(Contract).filter(Contract.id == visit.contract_id).first()
        if contract:
            all_visits = db.query(Visit).filter(Visit.contract_id == contract.id).all()
            completed_visits = [v for v in all_visits if v.status == "completed"]

            # If all visits are completed, mark contract as completed
            if len(completed_visits) == len(all_visits) and len(all_visits) > 0:
                contract.status = "completed"
                db.commit()
                logger.info(
                    f"✅ Contract {contract.id} automatically marked as completed (all {len(all_visits)} visits completed)"
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


@router.post("/{visit_id}/upload-photo", response_model=PhotoUploadResponse)
async def upload_visit_photo(
    visit_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a photo for visit completion proof"""
    import logging
    from ..routes.upload import upload_to_r2

    logger = logging.getLogger(__name__)

    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    # Check current photo count
    current_count = visit.photo_count or 0
    if current_count >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 photos allowed per visit")

    try:
        # Upload to R2
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"visit_{visit.public_id}_{current_count + 1}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        key = f"visits/{current_user.id}/{filename}"

        # Reset file pointer
        await file.seek(0)
        photo_key = await upload_to_r2(file, key)

        # Generate presigned URL
        from ..routes.upload import generate_presigned_url

        photo_url = generate_presigned_url(photo_key, expires_in=31536000)  # 1 year

        # Update visit with photo URL
        if visit.photo_proof_urls is None:
            visit.photo_proof_urls = []

        visit.photo_proof_urls.append(photo_url)
        visit.photo_count = len(visit.photo_proof_urls)
        visit.photos_uploaded_at = datetime.utcnow()

        db.commit()
        db.refresh(visit)

        logger.info(
            f"✅ Photo uploaded for visit {visit_id}: {photo_key} (count: {visit.photo_count})"
        )

        return PhotoUploadResponse(url=photo_url, key=photo_key, uploaded_at=datetime.utcnow())

    except Exception as e:
        logger.error(f"❌ Failed to upload photo for visit {visit_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload photo: {str(e)}")


@router.delete("/{visit_id}/photo/{photo_index}")
async def delete_visit_photo(
    visit_id: int,
    photo_index: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a photo from visit (before completion)"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if visit.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot delete photos from completed visit")

    if not visit.photo_proof_urls or photo_index >= len(visit.photo_proof_urls):
        raise HTTPException(status_code=404, detail="Photo not found")

    # Remove photo from array
    visit.photo_proof_urls.pop(photo_index)
    visit.photo_count = len(visit.photo_proof_urls)

    db.commit()

    return {"message": "Photo deleted successfully", "remaining_count": visit.photo_count}


@router.get("/all", response_model=List[VisitResponse])
async def get_all_visits_filtered(
    client_id: Optional[int] = None,
    contract_id: Optional[int] = None,
    status: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    week: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all visits with filters for the dedicated Visits Management page"""
    from sqlalchemy import and_, extract

    query = db.query(Visit).filter(Visit.user_id == current_user.id)

    # Apply filters
    if client_id:
        query = query.filter(Visit.client_id == client_id)

    if contract_id:
        query = query.filter(Visit.contract_id == contract_id)

    if status:
        query = query.filter(Visit.status == status)

    # Time-based filters
    if year and month:
        query = query.filter(
            and_(
                extract("year", Visit.scheduled_date) == year,
                extract("month", Visit.scheduled_date) == month,
            )
        )
    elif year:
        query = query.filter(extract("year", Visit.scheduled_date) == year)

    if week and year:
        query = query.filter(
            and_(
                extract("year", Visit.scheduled_date) == year,
                extract("week", Visit.scheduled_date) == week,
            )
        )

    # Order by scheduled date
    visits = query.order_by(Visit.scheduled_date.desc()).all()

    return [VisitResponse.from_orm(v) for v in visits]


@router.get("/grouped-by-contract")
async def get_visits_grouped_by_contract(
    month: Optional[int] = None,
    year: Optional[int] = None,
    week: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get visits grouped by contract and client for the Visits Management page"""
    from sqlalchemy import and_, extract
    from ..models import Client

    # Build base query
    query = db.query(Visit).filter(Visit.user_id == current_user.id)

    # Apply time filters (default to current month if not specified)
    if not year:
        year = datetime.utcnow().year
    if not month and not week:
        month = datetime.utcnow().month

    if month:
        query = query.filter(
            and_(
                extract("year", Visit.scheduled_date) == year,
                extract("month", Visit.scheduled_date) == month,
            )
        )
    elif week:
        query = query.filter(
            and_(
                extract("year", Visit.scheduled_date) == year,
                extract("week", Visit.scheduled_date) == week,
            )
        )

    if status:
        query = query.filter(Visit.status == status)

    # Get visits ordered by scheduled date
    visits = query.order_by(Visit.scheduled_date.asc()).all()

    # Group by contract
    grouped = {}
    for visit in visits:
        if visit.contract_id not in grouped:
            contract = db.query(Contract).filter(Contract.id == visit.contract_id).first()
            client = db.query(Client).filter(Client.id == visit.client_id).first()

            if contract and client:
                grouped[visit.contract_id] = {
                    "contract_id": contract.id,
                    "contract_title": contract.title,
                    "contract_status": contract.status,
                    "client_id": client.id,
                    "client_name": client.contact_name or client.business_name,
                    "client_email": client.email,
                    "visits": [],
                }

        if visit.contract_id in grouped:
            grouped[visit.contract_id]["visits"].append(VisitResponse.from_orm(visit))

    return {"contracts": list(grouped.values()), "total_visits": len(visits)}
