"""
Automated status transitions for contracts
Handles scheduled → active and active → completed transitions
"""

from datetime import datetime
from sqlalchemy.orm import Session
from ..models import Contract
import logging

logger = logging.getLogger(__name__)


def update_contract_statuses(db: Session) -> dict:
    """
    Update contract statuses based on dates
    Should be run as a scheduled job (e.g., daily cron)
    
    Returns:
        dict: Summary of status changes made
    """
    summary = {
        "scheduled_to_active": 0,
        "active_to_completed": 0,
        "total_updated": 0
    }
    
    try:
        now = datetime.utcnow()
        
        # 1. Update SCHEDULED → ACTIVE (start date has arrived)
        scheduled_contracts = db.query(Contract).filter(
            Contract.status == "scheduled",
            Contract.start_date <= now
        ).all()
        
        for contract in scheduled_contracts:
            contract.status = "active"
            summary["scheduled_to_active"] += 1
            logger.info(f"✅ Contract {contract.id} transitioned: scheduled → active")
        
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
        
        # Commit all changes
        if summary["scheduled_to_active"] > 0 or summary["active_to_completed"] > 0:
            db.commit()
            summary["total_updated"] = summary["scheduled_to_active"] + summary["active_to_completed"]
            logger.info(f"📊 Status automation summary: {summary}")
        else:
            logger.debug("ℹ️ No contract status updates needed")
        
        return summary
    
    except Exception as e:
        logger.error(f"❌ Error updating contract statuses: {str(e)}")
        db.rollback()
        raise


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if a status transition is allowed
    
    Args:
        current_status: Current contract status
        new_status: Desired new status
    
    Returns:
        bool: True if transition is valid, False otherwise
    """
    # Define valid transitions
    valid_transitions = {
        "new": ["signed", "cancelled"],
        "signed": ["scheduled", "cancelled"],
        "scheduled": ["active", "cancelled"],
        "active": ["completed", "cancelled"],
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
        return "Client needs to confirm schedule slot"
    
    elif contract.status == "scheduled":
        if contract.start_date:
            days_until_start = (contract.start_date - datetime.utcnow()).days
            if days_until_start > 0:
                return f"Service starts in {days_until_start} days"
            else:
                return "Service should start today - update to active status"
        return "Start date not set"
    
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
