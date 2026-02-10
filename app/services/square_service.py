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


async def _get_location_id(access_token: str, merchant_id: str) -> str:
    """
    Get the first active location_id for the merchant.
    Square requires a location_id for orders and invoices.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                f"{SQUARE_API_URL}/locations",
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch locations: {response.text}")
                # Fallback to merchant_id (might work for some accounts)
                return merchant_id
            
            locations_data = response.json()
            locations = locations_data.get("locations", [])
            
            # Find first active location
            for location in locations:
                if location.get("status") == "ACTIVE":
                    location_id = location.get("id")
                    logger.info(f"✅ Found active location: {location_id}")
                    return location_id
            
            # If no active location, use first location
            if locations:
                location_id = locations[0].get("id")
                logger.warning(f"⚠️ No active location found, using first location: {location_id}")
                return location_id
            
            # Last resort: use merchant_id
            logger.warning(f"⚠️ No locations found, falling back to merchant_id: {merchant_id}")
            return merchant_id
            
    except Exception as e:
        logger.error(f"Error fetching location_id: {e}")
        return merchant_id


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
        
        # Get the actual location_id (merchant_id is not the same as location_id)
        location_id = await _get_location_id(access_token, square_integration.merchant_id)
        
        # Prepare invoice data
        invoice_data = await _prepare_invoice_data(
            contract=contract,
            client=client,
            schedule=schedule,
            location_id=location_id,
            access_token=access_token
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
            
            # Publish the invoice (makes it active and generates payment link)
            # Note: With SHARE_MANUALLY delivery method, Square won't send emails
            publish_result = await _publish_square_invoice(invoice_id, access_token)
            if not publish_result.get("success"):
                logger.warning(f"⚠️ Failed to publish invoice {invoice_id}: {publish_result.get('message')}")
            else:
                logger.info(f"✅ Square invoice published (ready for manual sharing): {invoice_id}")
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_url": invoice_url,
                "published": publish_result.get("success", False),
                "message": "Square invoice created and ready for Cleanenroll to send"
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
    location_id: str,
    access_token: str
) -> Dict[str, Any]:
    """
    Prepare Square invoice data structure
    
    Square requires creating an Order first, then attaching it to the invoice.
    https://developer.squareup.com/reference/square/invoices-api/create-invoice
    """
    # Calculate due date (default 15 days from now)
    due_date = datetime.utcnow() + timedelta(days=15)
    
    # Step 1: Create an Order first
    service_description = contract.description or contract.title
    if schedule.service_type:
        service_description = f"{schedule.service_type.replace('-', ' ').title()} - {service_description}"
    
    order_data = {
        "order": {
            "location_id": location_id,  # Use actual location_id, not merchant_id
            "line_items": [
                {
                    "name": contract.title,
                    "quantity": "1",
                    "base_price_money": {
                        "amount": int(contract.total_value * 100),  # Convert to cents
                        "currency": contract.currency or "USD"
                    },
                    "note": service_description
                }
            ],
            "metadata": {
                "contract_id": str(contract.id),
                "schedule_id": str(schedule.id)
            }
        },
        "idempotency_key": f"order-{contract.id}-{int(datetime.utcnow().timestamp())}"
    }
    
    # Create the order
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        order_response = await http_client.post(
            f"{SQUARE_API_URL}/orders",
            json=order_data,
            headers={
                "Square-Version": "2024-12-18",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        if order_response.status_code not in [200, 201]:
            error_detail = order_response.text
            logger.error(f"Square order creation failed: {error_detail}")
            raise Exception(f"Failed to create Square order: {error_detail}")
        
        order_result = order_response.json()
        order_id = order_result.get("order", {}).get("id")
        
        if not order_id:
            raise Exception("No order ID returned from Square")
        
        logger.info(f"✅ Square order created: {order_id}")
    
    # Step 2: Create or get Square customer
    customer_id = await _get_or_create_square_customer(
        client=client,
        access_token=access_token
    )
    
    # Step 3: Create invoice with the order_id and customer_id
    # Use SHARE_MANUALLY so Cleanenroll handles all email communications
    invoice_data = {
        "invoice": {
            "location_id": location_id,  # Use actual location_id, not merchant_id
            "order_id": order_id,  # Reference the created order
            "primary_recipient": {
                "customer_id": customer_id  # Only customer_id, no other fields
            },
            "payment_requests": [
                {
                    "request_type": "BALANCE",
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "automatic_payment_source": "NONE"
                    # No reminders - Cleanenroll will handle all email communications
                }
            ],
            "delivery_method": "SHARE_MANUALLY",  # Cleanenroll sends emails, not Square
            "invoice_number": f"INV-{contract.public_id[:8].upper()}",  # Use secure random ID
            "title": contract.title,
            "description": f"Service scheduled for {schedule.scheduled_date.strftime('%B %d, %Y')} at {schedule.start_time}",
            # Don't set scheduled_at - not needed for manual sharing
            "accepted_payment_methods": {
                "card": True,
                "square_gift_card": False,
                "bank_account": False,
                "buy_now_pay_later": False,
                "cash_app_pay": True
            }
        },
        "idempotency_key": f"invoice-{contract.id}-{int(datetime.utcnow().timestamp())}"
    }
    
    return invoice_data


async def _get_or_create_square_customer(
    client: Client,
    access_token: str
) -> str:
    """
    Get existing Square customer or create a new one
    
    Returns:
        customer_id: Square customer ID
    """
    try:
        # First, try to search for existing customer by email
        if client.email:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                search_response = await http_client.post(
                    f"{SQUARE_API_URL}/customers/search",
                    json={
                        "query": {
                            "filter": {
                                "email_address": {
                                    "exact": client.email
                                }
                            }
                        }
                    },
                    headers={
                        "Square-Version": "2024-12-18",
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                )
                
                if search_response.status_code == 200:
                    search_result = search_response.json()
                    customers = search_result.get("customers", [])
                    if customers:
                        customer_id = customers[0].get("id")
                        logger.info(f"✅ Found existing Square customer: {customer_id}")
                        return customer_id
        
        # Customer not found, create new one
        customer_data = {
            "idempotency_key": f"customer-{client.id}-{int(datetime.utcnow().timestamp())}",
            "given_name": client.contact_name or client.business_name,
            "email_address": client.email,
            "phone_number": client.phone if client.phone else None,
            "company_name": client.business_name if client.contact_name else None,
            "reference_id": f"client-{client.id}"
        }
        
        # Remove None values
        customer_data = {k: v for k, v in customer_data.items() if v is not None}
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            create_response = await http_client.post(
                f"{SQUARE_API_URL}/customers",
                json=customer_data,
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if create_response.status_code not in [200, 201]:
                error_detail = create_response.text
                logger.error(f"Square customer creation failed: {error_detail}")
                raise Exception(f"Failed to create Square customer: {error_detail}")
            
            customer_result = create_response.json()
            customer_id = customer_result.get("customer", {}).get("id")
            
            if not customer_id:
                raise Exception("No customer ID returned from Square")
            
            logger.info(f"✅ Square customer created: {customer_id}")
            return customer_id
            
    except Exception as e:
        logger.error(f"Error getting/creating Square customer: {str(e)}")
        raise


async def _publish_square_invoice(
    invoice_id: str,
    access_token: str
) -> Dict[str, Any]:
    """
    Publish a Square invoice to send it to the customer
    
    Square invoices are created in DRAFT status and must be published
    to send them to customers via email.
    
    https://developer.squareup.com/reference/square/invoices-api/publish-invoice
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{SQUARE_API_URL}/invoices/{invoice_id}/publish",
                json={
                    "version": 0,  # Version 0 for newly created invoices
                    "idempotency_key": f"publish-{invoice_id}-{int(datetime.utcnow().timestamp())}"
                },
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"Square invoice publish failed: {error_detail}")
                return {
                    "success": False,
                    "message": f"Failed to publish invoice: {error_detail}"
                }
            
            logger.info(f"✅ Square invoice published: {invoice_id}")
            return {
                "success": True,
                "message": "Invoice published successfully"
            }
            
    except Exception as e:
        logger.error(f"Error publishing Square invoice {invoice_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


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
