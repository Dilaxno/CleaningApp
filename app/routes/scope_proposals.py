"""
Provider-Led Scope of Work Proposal Routes
Handles provider creation, client review, versioning, and PDF generation
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_with_plan
from ..database import get_db
from ..models import (
    Client,
    ScopeEmailReminder,
    ScopeProposal,
    ScopeProposalAuditLog,
    User,
)
from ..services.scope_email_service import (
    send_approval_notification_email,
    send_revision_request_notification_email,
    send_scope_review_email,
)
from ..services.scope_pdf_generator import generate_scope_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scope-proposals", tags=["scope-proposals"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================
class TaskSchema(BaseModel):
    id: str
    label: str
    frequency: str  # Daily, Weekly, Monthly, Periodic, Custom
    notes: Optional[str] = None


class ServiceAreaSchema(BaseModel):
    id: str
    name: str
    tasks: list[TaskSchema]


class CreateScopeProposalRequest(BaseModel):
    client_id: int
    service_areas: list[ServiceAreaSchema]
    provider_notes: Optional[str] = None


class SendScopeProposalRequest(BaseModel):
    proposal_id: int


class ClientReviewResponse(BaseModel):
    response: str  # approved / revision_requested
    revision_notes: Optional[str] = None


class ScopeProposalResponse(BaseModel):
    id: int
    public_id: str
    client_id: int
    version: str
    status: str
    scope_data: dict
    provider_notes: Optional[str]
    pdf_key: Optional[str]
    review_deadline: Optional[datetime]
    sent_at: Optional[datetime]
    viewed_at: Optional[datetime]
    client_response: Optional[str]
    client_response_at: Optional[datetime]
    client_revision_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def generate_review_token() -> str:
    """Generate secure review token for client access"""
    return secrets.token_urlsafe(48)


def calculate_version(parent_version: Optional[str]) -> str:
    """Calculate next version number"""
    if not parent_version:
        return "v1.0"

    # Parse version (e.g., "v1.2" -> major=1, minor=2)
    version_str = parent_version.lstrip("v")
    parts = version_str.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0

    # Increment minor version
    return f"v{major}.{minor + 1}"


def create_audit_log(
    db: Session,
    proposal_id: int,
    action: str,
    actor_type: str,
    actor_id: Optional[int] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Create audit log entry"""
    audit_log = ScopeProposalAuditLog(
        proposal_id=proposal_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        old_status=old_status,
        new_status=new_status,
        notes=notes,
        metadata=metadata,
    )
    db.add(audit_log)
    db.commit()


def schedule_email_reminders(db: Session, proposal: ScopeProposal):
    """Schedule email reminders for proposal"""
    if not proposal.review_deadline:
        return

    # 24-hour reminder
    reminder_24h = ScopeEmailReminder(
        proposal_id=proposal.id,
        reminder_type="24h_reminder",
        scheduled_for=proposal.review_deadline - timedelta(hours=24),
        status="pending",
    )
    db.add(reminder_24h)

    # 47-hour reminder (1 hour before deadline)
    reminder_47h = ScopeEmailReminder(
        proposal_id=proposal.id,
        reminder_type="47h_reminder",
        scheduled_for=proposal.review_deadline - timedelta(hours=1),
        status="pending",
    )
    db.add(reminder_47h)

    db.commit()


# ============================================================
# PROVIDER ENDPOINTS
# ============================================================
@router.post("/create", response_model=ScopeProposalResponse)
async def create_scope_proposal(
    request: CreateScopeProposalRequest,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """
    Provider creates a new scope proposal (draft state)
    """
    logger.info(f"📝 Creating scope proposal for client {request.client_id}")

    # Verify client belongs to provider
    client = (
        db.query(Client)
        .filter(Client.id == request.client_id, Client.user_id == current_user.id)
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or access denied",
        )

    # Check if there's a parent proposal (for versioning)
    parent_proposal = (
        db.query(ScopeProposal)
        .filter(
            ScopeProposal.client_id == request.client_id,
            ScopeProposal.user_id == current_user.id,
        )
        .order_by(ScopeProposal.created_at.desc())
        .first()
    )

    # Calculate version
    version = calculate_version(parent_proposal.version if parent_proposal else None)

    # Create scope data structure
    scope_data = {"serviceAreas": [area.model_dump() for area in request.service_areas]}

    # Create proposal
    proposal = ScopeProposal(
        user_id=current_user.id,
        client_id=request.client_id,
        version=version,
        parent_proposal_id=parent_proposal.id if parent_proposal else None,
        status="draft",
        scope_data=scope_data,
        provider_notes=request.provider_notes,
    )

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    # Create audit log
    create_audit_log(
        db=db,
        proposal_id=proposal.id,
        action="created",
        actor_type="provider",
        actor_id=current_user.id,
        new_status="draft",
        notes=f"Created {version}",
    )

    logger.info(f"✅ Created scope proposal {proposal.id} ({version})")

    return ScopeProposalResponse(
        id=proposal.id,
        public_id=proposal.public_id,
        client_id=proposal.client_id,
        version=proposal.version,
        status=proposal.status,
        scope_data=proposal.scope_data,
        provider_notes=proposal.provider_notes,
        pdf_key=proposal.pdf_key,
        review_deadline=proposal.review_deadline,
        sent_at=proposal.sent_at,
        viewed_at=proposal.viewed_at,
        client_response=proposal.client_response,
        client_response_at=proposal.client_response_at,
        client_revision_notes=proposal.client_revision_notes,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


@router.post("/send")
async def send_scope_proposal(
    request: SendScopeProposalRequest,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """
    Provider sends scope proposal to client for review
    Generates PDF, creates review link, schedules reminders
    """
    logger.info(f"📤 Sending scope proposal {request.proposal_id}")

    # Get proposal
    proposal = (
        db.query(ScopeProposal)
        .filter(
            ScopeProposal.id == request.proposal_id,
            ScopeProposal.user_id == current_user.id,
        )
        .first()
    )

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found or access denied",
        )

    if proposal.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send proposal in {proposal.status} status",
        )

    # Generate review token
    proposal.review_token = generate_review_token()
    proposal.review_deadline = datetime.utcnow() + timedelta(hours=48)
    proposal.status = "sent"
    proposal.sent_at = datetime.utcnow()

    # Generate PDF
    try:
        pdf_bytes, pdf_hash, pdf_key = await generate_scope_pdf(proposal, db)

        # Store PDF metadata
        proposal.pdf_key = pdf_key
        proposal.pdf_hash = pdf_hash
        proposal.pdf_generated_at = datetime.utcnow()

        logger.info(f"✅ Generated and uploaded PDF for proposal {proposal.id}")
    except Exception as e:
        logger.error(f"❌ Failed to generate PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF"
        )

    db.commit()

    # Schedule email reminders
    schedule_email_reminders(db, proposal)

    # Create audit log
    create_audit_log(
        db=db,
        proposal_id=proposal.id,
        action="sent",
        actor_type="provider",
        actor_id=current_user.id,
        old_status="draft",
        new_status="sent",
        notes="Sent to client for review",
    )

    # Send email to client
    try:
        await send_scope_review_email(proposal, db)
        logger.info(f"✅ Sent review email for proposal {proposal.id}")
    except Exception as e:
        logger.error(f"❌ Failed to send review email: {e}")
        # Don't fail the request if email fails

    logger.info(f"✅ Sent scope proposal {proposal.id} to client")

    return {"message": "Scope proposal sent successfully", "proposal_id": proposal.id}


@router.get("/list")
async def list_scope_proposals(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """
    List all scope proposals for provider
    """
    query = db.query(ScopeProposal).filter(ScopeProposal.user_id == current_user.id)

    if client_id:
        query = query.filter(ScopeProposal.client_id == client_id)

    if status:
        query = query.filter(ScopeProposal.status == status)

    proposals = query.order_by(ScopeProposal.created_at.desc()).all()

    return {
        "proposals": [
            ScopeProposalResponse(
                id=p.id,
                public_id=p.public_id,
                client_id=p.client_id,
                version=p.version,
                status=p.status,
                scope_data=p.scope_data,
                provider_notes=p.provider_notes,
                pdf_key=p.pdf_key,
                review_deadline=p.review_deadline,
                sent_at=p.sent_at,
                viewed_at=p.viewed_at,
                client_response=p.client_response,
                client_response_at=p.client_response_at,
                client_revision_notes=p.client_revision_notes,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in proposals
        ]
    }


# ============================================================
# CLIENT ENDPOINTS (PUBLIC)
# ============================================================
@router.get("/review/{review_token}")
async def get_scope_for_review(review_token: str, request: Request, db: Session = Depends(get_db)):
    """
    Client accesses scope proposal via secure review link
    """
    logger.info(f"👀 Client viewing scope proposal with token")

    proposal = db.query(ScopeProposal).filter(ScopeProposal.review_token == review_token).first()

    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid review link")

    # Check if expired
    if proposal.review_deadline and datetime.utcnow() > proposal.review_deadline:
        if proposal.status != "expired":
            proposal.status = "expired"
            db.commit()

            create_audit_log(
                db=db,
                proposal_id=proposal.id,
                action="expired",
                actor_type="system",
                old_status="sent",
                new_status="expired",
                notes="Review deadline passed",
            )

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This review link has expired. Please contact the provider.",
        )

    # Mark as viewed (first time only)
    if not proposal.viewed_at:
        proposal.viewed_at = datetime.utcnow()
        proposal.status = "viewed"
        proposal.client_ip = request.client.host
        proposal.client_user_agent = request.headers.get("user-agent", "")
        db.commit()

        create_audit_log(
            db=db,
            proposal_id=proposal.id,
            action="viewed",
            actor_type="client",
            old_status="sent",
            new_status="viewed",
            metadata={
                "ip": proposal.client_ip,
                "user_agent": proposal.client_user_agent,
            },
        )

    # Get client info
    client = db.query(Client).filter(Client.id == proposal.client_id).first()

    return {
        "proposal": ScopeProposalResponse(
            id=proposal.id,
            public_id=proposal.public_id,
            client_id=proposal.client_id,
            version=proposal.version,
            status=proposal.status,
            scope_data=proposal.scope_data,
            provider_notes=proposal.provider_notes,
            pdf_key=proposal.pdf_key,
            review_deadline=proposal.review_deadline,
            sent_at=proposal.sent_at,
            viewed_at=proposal.viewed_at,
            client_response=proposal.client_response,
            client_response_at=proposal.client_response_at,
            client_revision_notes=proposal.client_revision_notes,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
        ),
        "client": {
            "business_name": client.business_name,
            "contact_name": client.contact_name,
        },
    }


@router.post("/review/{review_token}/respond")
async def client_respond_to_scope(
    review_token: str,
    response: ClientReviewResponse,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Client approves or requests revision on scope proposal
    """
    logger.info(f"📝 Client responding to scope proposal: {response.response}")

    proposal = db.query(ScopeProposal).filter(ScopeProposal.review_token == review_token).first()

    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid review link")

    # Check if expired
    if proposal.review_deadline and datetime.utcnow() > proposal.review_deadline:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Review deadline has passed")

    # Check if already responded
    if proposal.client_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already responded to this proposal",
        )

    # Validate response
    if response.response not in ["approved", "revision_requested"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid response type")

    # Update proposal
    old_status = proposal.status
    proposal.client_response = response.response
    proposal.client_response_at = datetime.utcnow()
    proposal.client_revision_notes = response.revision_notes
    proposal.status = response.response  # approved or revision_requested

    db.commit()

    # Create audit log
    create_audit_log(
        db=db,
        proposal_id=proposal.id,
        action=response.response,
        actor_type="client",
        old_status=old_status,
        new_status=response.response,
        notes=response.revision_notes,
        metadata={"ip": request.client.host},
    )

    # Send notification email to provider
    try:
        if response.response == "approved":
            await send_approval_notification_email(proposal, db)
        elif response.response == "revision_requested":
            await send_revision_request_notification_email(proposal, db)
    except Exception as e:
        logger.error(f"❌ Failed to send notification email: {e}")
        # Don't fail the request if email fails

    logger.info(f"✅ Client {response.response} scope proposal {proposal.id}")

    return {
        "message": f"Scope proposal {response.response}",
        "status": proposal.status,
    }


# ============================================================
# ADMIN/UTILITY ENDPOINTS
# ============================================================
@router.get("/{proposal_id}/audit-log")
async def get_proposal_audit_log(
    proposal_id: int,
    current_user: User = Depends(get_current_user_with_plan),
    db: Session = Depends(get_db),
):
    """
    Get audit log for a proposal
    """
    # Verify access
    proposal = (
        db.query(ScopeProposal)
        .filter(ScopeProposal.id == proposal_id, ScopeProposal.user_id == current_user.id)
        .first()
    )

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found or access denied",
        )

    # Get audit logs
    logs = (
        db.query(ScopeProposalAuditLog)
        .filter(ScopeProposalAuditLog.proposal_id == proposal_id)
        .order_by(ScopeProposalAuditLog.created_at.desc())
        .all()
    )

    return {
        "audit_logs": [
            {
                "id": log.id,
                "action": log.action,
                "actor_type": log.actor_type,
                "actor_id": log.actor_id,
                "old_status": log.old_status,
                "new_status": log.new_status,
                "notes": log.notes,
                "metadata": log.metadata,
                "created_at": log.created_at,
            }
            for log in logs
        ]
    }
