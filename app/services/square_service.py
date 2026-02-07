"""
Square Invoice Service
Handles automatic Square invoice creation after schedule approval
"""
import logging
import httpx
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from ..models import Contract, Client, User, Schedule
from ..models_square import SquareIntegration
from ..config import SECRET_KEY

logger = logging.getLogger(__name__)

# Square Configuration
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
if SQUARE_ENVIRONMENT == "production":
    SQUARE_API_URL = "https://connect.squareup.com/v2"
else:
    SQUARE_API_URL = "https://connect.squareupsandbox.com/v2"

# Encryption for tokens
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b'='))


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


async def create_square_invoice_for_contract(
    contract: Contract,
    client: Client,
    schedule: Schedule,
    user: User,
    db: Session
) -> Dict[str, Any]:
    """
    Create a Square invoice after provider accepts the schedule
    
    Args:
        contract: The signed contract
        client: The client who will receive the invoice
        schedule: The accepted schedule
        user: The provider (business owner)
        db: Database session
        
    Returns:
        Dict with success status, invoice_id, and invoice_url
    """
    try:
        # Check if Square is connected for this user
        square_integration = db.query(SquareIntegration).filter(
            SquareIntegration.user_id == user.firebase_uid,
            SquareIntegration.is_active == True
        ).first()
        
        if not square_integration:
            logger.info(f"Square not connected for user {user.id}, skipping invoice creation")
            return {
                "success": False,
                "reason": "square_not_connected",
                "message": "Square integration not connected"
            }
        
        # Check if invoice already exists for this contract
        if contract.square_invoice_id:
            logger.info(f"Square invoice already exists for contract {contract.id}: {contract.square_invoice_id}")
            return {
                "success": False,
                "reason": "invoice_exists",
                "message": "Invoice already created",
                "invoice_id": contract.square_invoice_id,
                "invoice_url": contract.square_invoice_url
            }
        
        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)
        
        # Prepare invoice data
        invoice_data = await _prepare_invoice_data(
            contract=contract,
            client=client,
            schedule=schedule,
            merchant_id=square_integration.merchant_id
        )
        
        # Create Square invoice via API
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{SQUARE_API_URL}/invoices",
                json=invoice_data,
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"Square invoice creation failed: {error_detail}")
                return {
                    "success": False,
                    "reason": "api_error",
                    "message": f"Square API error: {error_detail}",
                    "status_code": response.status_code
                }
            
            invoice_response = response.json()
            invoice = invoice_response.get("invoice", {})
            
            invoice_id = invoice.get("id")
            invoice_url = invoice.get("public_url")
            
            if not invoice_id:
                logger.error(f"No invoice ID in Square response: {invoice_response}")
                return {
                    "success": False,
                    "reason": "invalid_response",
                    "message": "Invalid response from Square"
                }
            
            # Update contract with Square invoice details
            contract.square_invoice_id = invoice_id
            contract.square_invoice_url = invoice_url
            contract.square_payment_status = "pending"
            contract.square_invoice_created_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"✅ Square invoice created successfully: {invoice_id} for contract {contract.id}")
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_url": invoice_url,
                "message": "Square invoice created successfully"
            }
            
    except Exception as e:
        logger.error(f"Error creating Square invoice for contract {contract.id}: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "reason": "exception",
            "message": f"Error: {str(e)}"
        }


async def _prepare_invoice_data(
    contract: Contract,
    client: Client,
    schedule: Schedule,
    merchant_id: str
) -> Dict[str, Any]:
    """
    Prepare Square invoice data structure
    
    Square Invoice API structure:
    https://developer.squareup.com/reference/square/invoices-api/create-invoice
    """
    # Calculate due date (default 15 days from now)
    due_date = datetime.utcnow() + timedelta(days=15)
    
    # Prepare line items from contract
    line_items = []
    
    # Main service line item
    service_description = contract.description or contract.title
    if schedule.service_type:
        service_description = f"{schedule.service_type.replace('-', ' ').title()} - {service_description}"
    
    line_items.append({
        "name": contract.title,
        "description": service_description,
        "quantity": "1",
        "base_price_money": {
            "amount": int(contract.total_value * 100),  # Convert to cents
            "currency": contract.currency or "USD"
        }
    })
    
    # Prepare customer data
    primary_recipient = {
        "customer_id": None,  # We don't have Square customer IDs yet
        "given_name": client.contact_name or client.business_name,
        "email_address": client.email,
        "phone_number": client.phone if client.phone else None,
        "company_name": client.business_name if client.contact_name else None
    }
    
    # Remove None values
    primary_recipient = {k: v for k, v in primary_recipient.items() if v is not None}
    
    # Prepare invoice data
    invoice_data = {
        "invoice": {
            "location_id": merchant_id,  # Using merchant_id as location_id (may need adjustment)
            "order": {
                "location_id": merchant_id,
                "line_items": line_items,
                "customer_id": None  # Will be created automatically if not exists
            },
            "primary_recipient": primary_recipient,
            "payment_requests": [
                {
                    "request_type": "BALANCE",
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "automatic_payment_source": "NONE",  # Client pays manually via link
                    "reminders": [
                        {
                            "relative_scheduled_days": -1,  # 1 day before due date
                            "message": "Your payment is due tomorrow"
                        }
                    ]
                }
            ],
            "delivery_method": "EMAIL",
            "invoice_number": f"INV-{contract.id}",
            "title": contract.title,
            "description": f"Service scheduled for {schedule.scheduled_date.strftime('%B %d, %Y')} at {schedule.start_time}",
            "scheduled_at": datetime.utcnow().isoformat() + "Z",  # Send immediately
            "accepted_payment_methods": {
                "card": True,
                "square_gift_card": False,
                "bank_account": False,
                "buy_now_pay_later": False,
                "cash_app_pay": True
            }
        },
        "idempotency_key": f"contract-{contract.id}-{int(datetime.utcnow().timestamp())}"
    }
    
    return invoice_data


async def check_square_payment_status(
    contract: Contract,
    db: Session
) -> Optional[str]:
    """
    Check the payment status of a Square invoice
    
    Returns:
        Payment status: "paid", "pending", "failed", "cancelled", or None if not found
    """
    if not contract.square_invoice_id:
        return None
    
    try:
        # Get Square integration for the contract owner
        user = db.query(User).filter(User.id == contract.user_id).first()
        if not user:
            return None
        
        square_integration = db.query(SquareIntegration).filter(
            SquareIntegration.user_id == user.firebase_uid,
            SquareIntegration.is_active == True
        ).first()
        
        if not square_integration:
            return None
        
        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)
        
        # Get invoice from Square API
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{SQUARE_API_URL}/invoices/{contract.square_invoice_id}",
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get Square invoice status: {response.text}")
                return None
            
            invoice_data = response.json()
            invoice = invoice_data.get("invoice", {})
            status = invoice.get("status", "").lower()
            
            # Map Square status to our status
            status_map = {
                "paid": "paid",
                "unpaid": "pending",
                "scheduled": "pending",
                "draft": "pending",
                "canceled": "cancelled",
                "failed": "failed"
            }
            
            mapped_status = status_map.get(status, "pending")
            
            # Update contract if status changed
            if contract.square_payment_status != mapped_status:
                contract.square_payment_status = mapped_status
                db.commit()
                logger.info(f"Updated Square payment status for contract {contract.id}: {mapped_status}")
            
            return mapped_status
            
    except Exception as e:
        logger.error(f"Error checking Square payment status for contract {contract.id}: {str(e)}")
        return None
