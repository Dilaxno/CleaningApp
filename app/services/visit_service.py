"""
Visit Management Service
Handles visit generation, status updates, and billing automation
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from ..models import Client, Contract, User
from ..models_invoice import Invoice
from ..models_visit import Visit


class VisitService:
    """Service for managing contract visits"""

    @staticmethod
    def generate_visits_for_contract(
        db: Session, contract: Contract, limit: int = 10
    ) -> List[Visit]:
        """
        Generate upcoming visits for a contract based on frequency.
        Only generates a limited number at a time to avoid clutter.
        """
        if not contract.frequency or not contract.start_date:
            return []

        # Check how many visits already exist
        existing_visits = (
            db.query(Visit)
            .filter(Visit.contract_id == contract.id)
            .order_by(desc(Visit.visit_number))
            .all()
        )

        # Determine starting point
        if existing_visits:
            last_visit = existing_visits[0]
            next_visit_number = last_visit.visit_number + 1
            next_date = last_visit.scheduled_date
        else:
            next_visit_number = 1
            next_date = contract.start_date

        # Calculate frequency interval
        frequency_map = {
            "daily": timedelta(days=1),
            "2x-per-week": timedelta(days=3.5),
            "3x-per-week": timedelta(days=2.33),
            "weekly": timedelta(weeks=1),
            "bi-weekly": timedelta(weeks=2),
            "monthly": timedelta(days=30),
        }

        interval = frequency_map.get(contract.frequency, timedelta(weeks=1))

        # Generate visits up to limit
        new_visits = []
        for i in range(limit):
            if existing_visits and i == 0:
                # Skip first iteration if we have existing visits
                next_date = next_date + interval
                continue

            # Check if we've exceeded contract end date
            if contract.end_date and next_date > contract.end_date:
                break

            visit = Visit(
                user_id=contract.user_id,
                client_id=contract.client_id,
                contract_id=contract.id,
                visit_number=next_visit_number + i,
                title=f"{contract.title} - Visit #{next_visit_number + i}",
                description=contract.description,
                scheduled_date=next_date,
                visit_amount=(
                    contract.total_value / self._calculate_total_visits(contract)
                    if contract.total_value
                    else None
                ),
                status="scheduled",
            )

            db.add(visit)
            new_visits.append(visit)
            next_date = next_date + interval

        db.commit()
        return new_visits

    @staticmethod
    def _calculate_total_visits(contract: Contract) -> int:
        """Calculate total number of visits for a contract based on frequency and duration"""
        if not contract.frequency or not contract.start_date or not contract.end_date:
            return 1

        duration_days = (contract.end_date - contract.start_date).days

        frequency_visits_per_month = {
            "daily": 30,
            "2x-per-week": 8,
            "3x-per-week": 12,
            "weekly": 4,
            "bi-weekly": 2,
            "monthly": 1,
        }

        visits_per_month = frequency_visits_per_month.get(contract.frequency, 4)
        total_months = duration_days / 30
        return max(1, int(total_months * visits_per_month))

    @staticmethod
    def get_upcoming_visits(db: Session, contract_id: int, limit: int = 10) -> List[Visit]:
        """Get upcoming visits for a contract"""
        return (
            db.query(Visit)
            .filter(
                and_(
                    Visit.contract_id == contract_id,
                    Visit.status.in_(["scheduled", "in_progress"]),
                    Visit.scheduled_date >= datetime.now(),
                )
            )
            .order_by(Visit.scheduled_date)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_past_visits(db: Session, contract_id: int) -> List[Visit]:
        """Get past/completed visits for a contract"""
        return (
            db.query(Visit)
            .filter(
                and_(
                    Visit.contract_id == contract_id,
                    Visit.status.in_(["completed", "payment_processing", "closed"]),
                )
            )
            .order_by(desc(Visit.scheduled_date))
            .all()
        )

    @staticmethod
    def start_visit(db: Session, visit_id: int, user_id: str) -> Visit:
        """Mark a visit as in progress"""
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise ValueError("Visit not found")

        if visit.status != "scheduled":
            raise ValueError("Visit must be in scheduled status to start")

        visit.status = "in_progress"
        visit.actual_start_time = datetime.now()
        visit.started_by = user_id
        visit.started_at = datetime.now()

        db.commit()
        db.refresh(visit)
        return visit

    @staticmethod
    def complete_visit(
        db: Session, visit_id: int, user_id: str, completion_notes: Optional[str] = None
    ) -> Visit:
        """Mark a visit as complete and trigger billing"""
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise ValueError("Visit not found")

        if visit.status != "in_progress":
            raise ValueError("Visit must be in progress to complete")

        visit.status = "completed"
        visit.actual_end_time = datetime.now()
        visit.completed_by = user_id
        visit.completed_at = datetime.now()
        visit.completion_notes = completion_notes

        db.commit()
        db.refresh(visit)

        # Trigger billing automation
        VisitService._trigger_billing(db, visit)

        return visit

    @staticmethod
    def _trigger_billing(db: Session, visit: Visit):
        """Trigger billing logic based on contract payment terms"""
        contract = db.query(Contract).filter(Contract.id == visit.contract_id).first()
        if not contract:
            return

        # Check payment terms to determine billing method
        payment_terms = contract.payment_terms or ""

        # If contract uses Square subscription, payment is automatic
        if contract.square_subscription_id:
            visit.status = "payment_processing"
            visit.payment_method = "square_subscription"
            visit.payment_status = "pending"
            db.commit()
            return

        # If manual payment or per-visit billing, create invoice
        if "per visit" in payment_terms.lower() or "manual" in payment_terms.lower():
            invoice = VisitService._create_visit_invoice(db, visit)
            if invoice:
                visit.invoice_id = invoice.id
                visit.status = "payment_processing"
                visit.payment_status = "pending"
                db.commit()

    @staticmethod
    def _create_visit_invoice(db: Session, visit: Visit) -> Optional[Invoice]:
        """Create an invoice for a completed visit"""
        contract = db.query(Contract).filter(Contract.id == visit.contract_id).first()
        if not contract:
            return None

        # Generate invoice number
        last_invoice = (
            db.query(Invoice)
            .filter(Invoice.user_id == visit.user_id)
            .order_by(desc(Invoice.id))
            .first()
        )

        if last_invoice and last_invoice.invoice_number:
            try:
                last_num = int(last_invoice.invoice_number.split("-")[-1])
                invoice_number = f"INV-{last_num + 1:05d}"
            except (ValueError, IndexError):
                invoice_number = f"INV-{visit.id:05d}"
        else:
            invoice_number = f"INV-{visit.id:05d}"

        invoice = Invoice(
            user_id=visit.user_id,
            client_id=visit.client_id,
            contract_id=visit.contract_id,
            invoice_number=invoice_number,
            title=f"Invoice for {visit.title}",
            description=visit.description,
            service_type=contract.frequency,
            base_amount=visit.visit_amount or 0,
            total_amount=visit.visit_amount or 0,
            status="pending",
            is_recurring=False,
            due_date=datetime.now() + timedelta(days=15),
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        return invoice

    @staticmethod
    def auto_generate_next_visits(db: Session, contract_id: int):
        """
        Automatically generate next batch of visits when upcoming visits are running low.
        Called after a visit is completed or when viewing the visit list.
        """
        upcoming_count = (
            db.query(Visit)
            .filter(
                and_(
                    Visit.contract_id == contract_id,
                    Visit.status == "scheduled",
                    Visit.scheduled_date >= datetime.now(),
                )
            )
            .count()
        )

        # If less than 3 upcoming visits, generate more
        if upcoming_count < 3:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                VisitService.generate_visits_for_contract(db, contract, limit=5)
