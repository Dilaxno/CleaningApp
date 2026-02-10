"""
Payout Routes for Service Provider Payment Tracking
"""
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ..database import get_db
from ..models import User, Client
from ..models_invoice import Invoice, Payout
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payouts", tags=["Payouts"])

class PayoutRequest(BaseModel):
    invoice_ids: List[int]
    payout_method: str = "bank_transfer"  # "bank_transfer" | "paypal"
    payout_details: Optional[dict] = None  # e.g., {"bank_name": "...", "account_holder": "...", "account_number": "...", "routing_number": "..."} or {"paypal_email": "..."}
    notes: Optional[str] = None

class PayoutResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    invoice_ids: List[int]
    payout_method: Optional[str]
    requested_at: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    reference_id: Optional[str]
    notes: Optional[str]

class PaymentSummary(BaseModel):
    total_received: float
    total_pending: float
    total_available: float
    total_paid_out: float
    currency: str

class ClientPaymentInfo(BaseModel):
    client_id: int
    client_name: str
    total_paid: float
    total_pending: float
    last_payment_date: Optional[datetime]
    invoice_count: int

@router.get("/summary", response_model=PaymentSummary)
async def get_payment_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment summary for the service provider"""
    # Total received (paid invoices)
    total_received = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == "paid"
    ).scalar() or 0
    
    # Total pending (sent but not paid)
    total_pending = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.user_id == current_user.id,
        Invoice.status.in_(["pending", "sent"])
    ).scalar() or 0
    
    # Total paid out
    total_paid_out = db.query(func.sum(Payout.amount)).filter(
        Payout.user_id == current_user.id,
        Payout.status == "completed"
    ).scalar() or 0
    
    # Available for payout (received - paid out)
    total_available = total_received - total_paid_out
    
    return PaymentSummary(
        total_received=total_received,
        total_pending=total_pending,
        total_available=max(0, total_available),
        total_paid_out=total_paid_out,
        currency="USD"
    )

@router.get("/client-payments", response_model=List[ClientPaymentInfo])
async def get_client_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment breakdown by client"""
    # Get all clients with their payment info
    clients = db.query(Client).filter(Client.user_id == current_user.id).all()
    
    result = []
    for client in clients:
        # Get paid amount
        total_paid = db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.client_id == client.id,
            Invoice.status == "paid"
        ).scalar() or 0
        
        # Get pending amount
        total_pending = db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.client_id == client.id,
            Invoice.status.in_(["pending", "sent"])
        ).scalar() or 0
        
        # Get last payment date
        last_payment = db.query(Invoice.paid_at).filter(
            Invoice.client_id == client.id,
            Invoice.status == "paid"
        ).order_by(Invoice.paid_at.desc()).first()
        
        # Get invoice count
        invoice_count = db.query(Invoice).filter(
            Invoice.client_id == client.id
        ).count()
        
        if invoice_count > 0 or total_paid > 0 or total_pending > 0:
            result.append(ClientPaymentInfo(
                client_id=client.id,
                client_name=client.business_name or client.contact_name or "Unknown",
                total_paid=total_paid,
                total_pending=total_pending,
                last_payment_date=last_payment[0] if last_payment else None,
                invoice_count=invoice_count
            ))
    
    return result

@router.get("/history", response_model=List[PayoutResponse])
async def get_payout_history(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payout history for the service provider"""
    query = db.query(Payout).filter(Payout.user_id == current_user.id)
    
    if status:
        query = query.filter(Payout.status == status)
    
    payouts = query.order_by(Payout.requested_at.desc()).all()
    
    return [PayoutResponse(
        id=p.id,
        amount=p.amount,
        currency=p.currency,
        status=p.status,
        invoice_ids=p.invoice_ids or [],
        payout_method=p.payout_method,
        requested_at=p.requested_at,
        processed_at=p.processed_at,
        completed_at=p.completed_at,
        reference_id=p.reference_id,
        notes=p.notes
    ) for p in payouts]

@router.post("/request", response_model=PayoutResponse)
async def request_payout(
    data: PayoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request a payout for paid invoices"""
    if not data.invoice_ids:
        raise HTTPException(status_code=400, detail="No invoices selected for payout")
    
    # Verify all invoices belong to user and are paid
    invoices = db.query(Invoice).filter(
        Invoice.id.in_(data.invoice_ids),
        Invoice.user_id == current_user.id,
        Invoice.status == "paid"
    ).all()
    
    if len(invoices) != len(data.invoice_ids):
        raise HTTPException(
            status_code=400, 
            detail="Some invoices are not found, not paid, or don't belong to you"
        )
    
    # Check if any invoice is already in a pending payout
    existing_payouts = db.query(Payout).filter(
        Payout.user_id == current_user.id,
        Payout.status.in_(["pending", "processing"])
    ).all()
    
    for payout in existing_payouts:
        for inv_id in data.invoice_ids:
            if inv_id in (payout.invoice_ids or []):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invoice {inv_id} is already in a pending payout request"
                )
    
    # Calculate total amount
    total_amount = sum(inv.total_amount for inv in invoices)
    
    # Create payout request
    payout = Payout(
        user_id=current_user.id,
        amount=total_amount,
        currency="USD",
        status="pending",
        invoice_ids=data.invoice_ids,
        payout_method=data.payout_method,
        payout_details=data.payout_details,
        notes=data.notes,
        requested_at=datetime.utcnow()
    )
    
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return PayoutResponse(
        id=payout.id,
        amount=payout.amount,
        currency=payout.currency,
        status=payout.status,
        invoice_ids=payout.invoice_ids or [],
        payout_method=payout.payout_method,
        requested_at=payout.requested_at,
        processed_at=payout.processed_at,
        completed_at=payout.completed_at,
        reference_id=payout.reference_id,
        notes=payout.notes
    )

@router.get("/available-invoices")
async def get_available_invoices_for_payout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get paid invoices available for payout"""
    # Get all pending payout invoice IDs
    pending_payouts = db.query(Payout).filter(
        Payout.user_id == current_user.id,
        Payout.status.in_(["pending", "processing"])
    ).all()
    
    excluded_ids = set()
    for payout in pending_payouts:
        excluded_ids.update(payout.invoice_ids or [])
    
    # Get paid invoices not in pending payouts
    query = db.query(Invoice).filter(
        Invoice.user_id == current_user.id,
        Invoice.status == "paid"
    )
    
    if excluded_ids:
        query = query.filter(~Invoice.id.in_(excluded_ids))
    
    invoices = query.order_by(Invoice.paid_at.desc()).all()
    
    result = []
    for inv in invoices:
        client = db.query(Client).filter(Client.id == inv.client_id).first()
        result.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "client_name": client.business_name if client else "Unknown",
            "total_amount": inv.total_amount,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None
        })
    
    return result

@router.get("/last-method")
async def get_last_payout_method(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return the most recently used payout method and details for pre-filling forms"""
    last = db.query(Payout).filter(Payout.user_id == current_user.id).order_by(Payout.requested_at.desc()).first()
    if not last:
        return {"payout_method": None, "payout_details": None}
    return {
        "payout_method": last.payout_method,
        "payout_details": last.payout_details or None
    }
