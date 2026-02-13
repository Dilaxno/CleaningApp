import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Contract, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contract Revisions"])


class RevisionRequest(BaseModel):
    revision_type: str  # 'pricing', 'scope', 'both'
    revision_notes: str
    custom_quote: Optional[dict[str, Any]] = None
    custom_scope: Optional[dict[str, Any]] = None


class RevisionResponse(BaseModel):
    id: int
    revision_requested: bool
    revision_type: Optional[str]
    revision_notes: Optional[str]
    revision_count: int
    custom_quote: Optional[dict[str, Any]]
    custom_scope: Optional[dict[str, Any]]
    revision_requested_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("/{contract_id}/request-revision", response_model=RevisionResponse)
async def request_contract_revision(
    contract_id: int,
    revision: RevisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider requests changes to contract before signing.
    This sends the contract back to the client for review with proposed changes.
    """
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Prevent revision if already signed by provider
    if contract.provider_signature:
        raise HTTPException(
            status_code=400, detail="Cannot request revision after provider has signed"
        )

    # Prevent infinite revision loops (max 5 revisions)
    if contract.revision_count >= 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum revision limit reached. Please contact client directly.",
        )

    # Validate revision type
    if revision.revision_type not in ["pricing", "scope", "both"]:
        raise HTTPException(
            status_code=400, detail="revision_type must be 'pricing', 'scope', or 'both'"
        )

    # Validate custom quote if pricing revision
    if revision.revision_type in ["pricing", "both"]:
        if not revision.custom_quote:
            raise HTTPException(
                status_code=400, detail="custom_quote required when requesting pricing changes"
            )

    # Validate custom scope if scope revision
    if revision.revision_type in ["scope", "both"]:
        if not revision.custom_scope:
            raise HTTPException(
                status_code=400, detail="custom_scope required when requesting scope changes"
            )

    # Update contract with revision request
    contract.revision_requested = True
    contract.revision_type = revision.revision_type
    contract.revision_notes = revision.revision_notes
    contract.revision_requested_at = datetime.now()
    contract.revision_count += 1

    if revision.custom_quote:
        contract.custom_quote = revision.custom_quote

    if revision.custom_scope:
        contract.custom_scope = revision.custom_scope

    # Reset status to 'new' so client sees it as pending their approval
    contract.status = "pending_revision"

    db.commit()
    db.refresh(contract)

    # TODO: Send email notification to client about revision request
    return RevisionResponse(
        id=contract.id,
        revision_requested=contract.revision_requested,
        revision_type=contract.revision_type,
        revision_notes=contract.revision_notes,
        revision_count=contract.revision_count,
        custom_quote=contract.custom_quote,
        custom_scope=contract.custom_scope,
        revision_requested_at=contract.revision_requested_at,
    )


@router.post("/{contract_id}/approve-revision")
async def approve_contract_revision(contract_id: int, db: Session = Depends(get_db)):
    """
    Client approves the provider's requested changes.
    This allows the contract to proceed to signing.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.revision_requested:
        raise HTTPException(status_code=400, detail="No revision pending for this contract")

    # Client has approved the changes - clear revision flags
    contract.revision_requested = False
    contract.status = "new"  # Ready for provider to sign

    # Keep the custom quote/scope but clear the revision request
    # revision_type, revision_notes, etc. stay for audit trail

    db.commit()
    db.refresh(contract)
    return {
        "message": "Revision approved successfully",
        "contract_id": contract.id,
        "status": contract.status,
    }


@router.post("/{contract_id}/reject-revision")
async def reject_contract_revision(
    contract_id: int, rejection_notes: Optional[str] = None, db: Session = Depends(get_db)
):
    """
    Client rejects the provider's requested changes.
    Provider can either accept original terms or request new revision.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.revision_requested:
        raise HTTPException(status_code=400, detail="No revision pending for this contract")

    # Client rejected - clear custom changes but keep in notes for reference
    contract.revision_requested = False
    contract.status = "new"  # Back to provider to either accept or revise again

    # Store rejection in notes for audit
    rejection_msg = f"\n\n[Client rejected revision on {datetime.now().strftime('%Y-%m-%d %H:%M')}]"
    if rejection_notes:
        rejection_msg += f"\nClient notes: {rejection_notes}"

    contract.revision_notes = (contract.revision_notes or "") + rejection_msg

    # Clear custom quote/scope since they were rejected
    contract.custom_quote = None
    contract.custom_scope = None

    db.commit()
    db.refresh(contract)
    return {
        "message": "Revision rejected. Contract returned to original terms.",
        "contract_id": contract.id,
        "status": contract.status,
    }


@router.get("/{contract_id}/revision-history")
async def get_revision_history(
    contract_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get revision history for a contract"""
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return {
        "contract_id": contract.id,
        "revision_count": contract.revision_count,
        "current_revision_pending": contract.revision_requested,
        "revision_type": contract.revision_type,
        "revision_notes": contract.revision_notes,
        "revision_requested_at": contract.revision_requested_at,
        "custom_quote": contract.custom_quote,
        "custom_scope": contract.custom_scope,
    }
