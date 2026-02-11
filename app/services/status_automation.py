"""
Automated status transitions for contracts and clients
Handles signed → active and active → completed transitions for contracts
Handles scheduled → active transitions for clients
"""

from datetime import datetime
from sqlalchemy.orm import Session
from ..models import Contract
import logging

logger = logging.getLogger(__name__)


def update_contract_statuses(db: Session) -> dict:
    """
    Update contract and client statuses based on dates
    Should be run as a scheduled job (e.g., daily cron)
    
    Contract statuses: new → signed → active → completed/cancelled
    Client statuses: new_lead → contacted → scheduled → active → completed
    
    Returns:
        dict: Summary of status changes made
    """
    from ..models import Client, Schedule
    
    summary = {
        "signed_to_active": 0,
        "active_to_completed": 0,
        "clients_to_active": 0,
        "total_updated": 0
    }
    
    try:
        now = datetime.utcnow()
        today = now.date()
        
        # 1. Update SIGNED → ACTIVE (start date has arrived)
        # Contracts become active when their start date arrives
        signed_contracts = db.query(Contract).filter(
            Contract.status == "signed",
            Contract.start_date <= now
        ).all()
        
        for contract in signed_contracts:
            contract.status = "active"
            summary["signed_to_active"] += 1
            logger.info(f"✅ Contract {contract.id} transitioned: signed → active")
        
        # 2. Update ACTIVE → COMPLETED (end date has passed)
        active_contracts = db.query(Contract).filter(
            Contract.status == "active",
            Contract.end_date.isnot(None),
            Contract.end_date <= now
        ).all()
        
        for contract in active_contracts:
            contract.status = "completed"
            summary["active_to_completed"] += 1
            logger.info(f"✅ Contract {contract.id} transitioned: active → completed")
        
        # 3. Update Client status to 'active' when first accepted schedule date arrives
        scheduled_clients = db.query(Client).filter(
            Client.status == "scheduled"
        ).all()
        
        for client in scheduled_clients:
            # Check if there's an accepted schedule for today or earlier
            first_schedule = db.query(Schedule).filter(
                Schedule.client_id == client.id,
                Schedule.approval_status == "accepted",
                Schedule.scheduled_date <= today
            ).order_by(Schedule.scheduled_date.asc()).first()
            
            if first_schedule:
                client.status = "active"
                summary["clients_to_active"] += 1
                logger.info(f"✅ Client {client.id} transitioned: scheduled → active (schedule {first_schedule.id} date arrived)")
        
        # Commit all changes
        total = sum([summary["signed_to_active"], summary["active_to_completed"], summary["clients_to_active"]])
        if total > 0:
            db.commit()
            summary["total_updated"] = total
            logger.info(f"📊 Status automation summary: {summary}")
        else:
            logger.debug("ℹ️ No contract/client status updates needed")
        
        return summary
    
    except Exception as e:
        logger.error(f"❌ Error updating contract statuses: {str(e)}")
        db.rollback()
        raise


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if a contract status transition is allowed
    
    Contract statuses: new → signed → active → completed/cancelled
    
    Note: 
    - 'completed' status is automatic only (set by system when end_date passes)
    - 'cancelled' status is manual only (requires owner action)
    
    Args:
        current_status: Current contract status
        new_status: Desired new status
    
    Returns:
        bool: True if transition is valid, False otherwise
    """
    # Define valid manual transitions for contracts
    valid_transitions = {
        "new": ["signed", "cancelled"],
        "signed": ["active", "cancelled"],
        "active": ["cancelled"],  # Only cancellation allowed manually; completion is automatic
        "cancelled": [],  # Terminal state
        "completed": []   # Terminal state
    }
    
    # Allow same status (no-op)
    if current_status == new_status:
        return True
    
    # Check if transition is valid
    return new_status in valid_transitions.get(current_status, [])


def get_next_required_action(contract: Contract) -> str:
    """
    Determine what action is required next for a contract
    
    Args:
        contract: Contract model instance
    
    Returns:
        str: Description of next required action
    """
    if contract.status == "new":
        if not contract.provider_signature:
            return "Provider needs to review and sign contract"
        elif not contract.client_signature:
            return "Waiting for client signature"
        else:
            return "Contract ready to be marked as signed"
    
    elif contract.status == "signed":
        if contract.start_date:
            days_until_start = (contract.start_date - datetime.utcnow()).days
            if days_until_start > 0:
                return f"Service starts in {days_until_start} days"
            else:
                return "Service should start today - update to active status"
        return "Waiting for service to begin"
    
    elif contract.status == "active":
        if contract.end_date:
            days_until_end = (contract.end_date - datetime.utcnow()).days
            if days_until_end > 0:
                return f"Service ongoing - {days_until_end} days remaining"
            else:
                return "Service period ended - ready to mark as completed"
        return "Service in progress (no end date)"
    
    elif contract.status == "cancelled":
        return "Contract was cancelled"
    
    elif contract.status == "completed":
        return "Service completed"
    
    return "Unknown status"
