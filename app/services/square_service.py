"""
Square Checkout Service
Handles Square Checkout API integration for job deposit payments
Uses Square Checkout instead of hosted invoice pages for better UX
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, SECRET_KEY
from ..models import Client, Contract, Schedule, User
from ..models_square import SquareIntegration

logger = logging.getLogger(__name__)

# Square Configuration
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
if SQUARE_ENVIRONMENT == "production":
    SQUARE_API_URL = "https://connect.squareup.com/v2"
else:
    SQUARE_API_URL = "https://connect.squareupsandbox.com/v2"

# Encryption for tokens
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


async def create_square_invoice_for_contract(
    contract: Contract,
    client: Client,
    schedule: Schedule,
    user: User,
    db: Session,
) -> dict[str, Any]:
    """
    Create Square Checkout session for contract deposit payment

    This replaces the old invoice-based flow with Square Checkout API.
    Creates a checkout link under the merchant's Square account and redirects
    to CleanEnroll after payment completion.

    Args:
        contract: The contract requiring payment
        client: The client who will pay
        schedule: The schedule associated with the contract
        user: The provider (business owner)
        db: Database session

    Returns:
        Dict with success status, checkout_url, and payment_link_id
    """
    try:
        # Check if Square is connected
        square_integration = (
            db.query(SquareIntegration)
            .filter(
                SquareIntegration.user_id == user.firebase_uid,
                SquareIntegration.is_active == True,
            )
            .first()
        )

        if not square_integration:
            logger.info(f"Square not connected for user {user.id}, skipping checkout creation")
            return {
                "success": False,
                "reason": "square_not_connected",
                "message": "Square integration not connected",
            }

        # Check if checkout already created
        if contract.square_invoice_id:
            logger.info(
                f"Checkout already exists for contract {contract.id}: {contract.square_invoice_id}"
            )
            return {
                "success": False,
                "reason": "checkout_exists",
                "message": "Checkout already created",
                "checkout_url": contract.square_invoice_url,
            }

        # Calculate deposit amount (50% of total)
        deposit_amount = contract.total_value / 2 if contract.total_value else 0
        remaining_balance = contract.total_value - deposit_amount if contract.total_value else 0

        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)

        # Create checkout session
        checkout_result = await _create_checkout_session(
            access_token=access_token,
            merchant_id=square_integration.merchant_id,
            contract=contract,
            client=client,
            deposit_amount=deposit_amount,
        )

        if not checkout_result.get("success"):
            return checkout_result

        payment_link_id = checkout_result["payment_link_id"]
        checkout_url = checkout_result["checkout_url"]

        # Update contract with checkout details
        contract.square_invoice_id = payment_link_id
        contract.square_invoice_url = checkout_url
        contract.square_invoice_created_at = datetime.utcnow()
        contract.square_payment_status = "pending"
        contract.deposit_amount = deposit_amount
        contract.remaining_balance = remaining_balance

        db.commit()

        logger.info(f"✅ Square Checkout created for contract {contract.id}: {payment_link_id}")

        return {
            "success": True,
            "payment_link_id": payment_link_id,
            "checkout_url": checkout_url,
            "deposit_amount": deposit_amount,
        }

    except Exception as e:
        logger.error(f"Error creating Square Checkout for contract {contract.id}: {str(e)}")
        logger.exception(e)
        db.rollback()
        return {
            "success": False,
            "reason": "exception",
            "message": f"Error: {str(e)}",
        }


async def _create_checkout_session(
    access_token: str,
    merchant_id: str,
    contract: Contract,
    client: Client,
    deposit_amount: float,
) -> dict[str, Any]:
    """
    Create Square Checkout payment link

    Uses Square Payment Links API to create a checkout session that redirects
    back to CleanEnroll after payment completion.
    """
    try:
        # Generate idempotency key
        idempotency_key = str(uuid.uuid4())

        # Build redirect URL with contract metadata
        redirect_url = (
            f"{FRONTEND_URL}/payment-result"
            f"?contract_id={contract.public_id or contract.id}"
            f"&client_id={client.id}"
        )

        # Create order for the checkout
        order_payload = {
            "idempotency_key": f"order-{contract.id}-{int(datetime.utcnow().timestamp())}",
            "order": {
                "location_id": merchant_id,
                "line_items": [
                    {
                        "name": f"{contract.title} - Deposit (50%)",
                        "quantity": "1",
                        "base_price_money": {
                            "amount": int(deposit_amount * 100),  # Convert to cents
                            "currency": contract.currency or "USD",
                        },
                        "note": f"Deposit payment for contract {contract.public_id or contract.id}",
                    }
                ],
                "metadata": {
                    "contract_id": str(contract.id),
                    "contract_public_id": contract.public_id or "",
                    "client_id": str(client.id),
                    "provider_id": str(contract.user_id),
                    "payment_type": "deposit",
                    "deposit_percentage": "50",
                },
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Create order
            logger.info(f"Creating Square order for contract {contract.id}")
            order_response = await http_client.post(
                f"{SQUARE_API_URL}/orders",
                json=order_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Square-Version": "2024-12-18",
                },
            )

            if order_response.status_code != 200:
                error_text = order_response.text
                logger.error(f"Failed to create Square order: {error_text}")
                return {
                    "success": False,
                    "reason": "order_creation_failed",
                    "message": f"Failed to create order: {error_text}",
                }

            order = order_response.json()["order"]
            order_id = order["id"]

            # Create payment link (checkout session)
            payment_link_payload = {
                "idempotency_key": idempotency_key,
                "order_id": order_id,
                "checkout_options": {
                    "redirect_url": redirect_url,
                    "ask_for_shipping_address": False,
                    "merchant_support_email": client.email or "",
                    "accepted_payment_methods": {
                        "apple_pay": True,
                        "google_pay": True,
                        "cash_app_pay": True,
                        "afterpay_clearpay": False,
                    },
                },
                "pre_populated_data": {
                    "buyer_email": client.email or "",
                    "buyer_phone_number": client.phone or "",
                },
                "payment_note": f"Deposit for {contract.title}",
            }

            logger.info(f"Creating Square Payment Link for order {order_id}")
            payment_link_response = await http_client.post(
                f"{SQUARE_API_URL}/online-checkout/payment-links",
                json=payment_link_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Square-Version": "2024-12-18",
                },
            )

            if payment_link_response.status_code not in [200, 201]:
                error_text = payment_link_response.text
                logger.error(f"Failed to create Square Payment Link: {error_text}")
                return {
                    "success": False,
                    "reason": "payment_link_creation_failed",
                    "message": f"Failed to create payment link: {error_text}",
                }

            payment_link_data = payment_link_response.json()
            payment_link = payment_link_data.get("payment_link", {})

            payment_link_id = payment_link.get("id")
            checkout_url = payment_link.get("url")

            if not payment_link_id or not checkout_url:
                logger.error(f"Invalid payment link response: {payment_link_data}")
                return {
                    "success": False,
                    "reason": "invalid_response",
                    "message": "Invalid response from Square",
                }

            logger.info(f"✅ Square Payment Link created: {payment_link_id}")

            return {
                "success": True,
                "payment_link_id": payment_link_id,
                "checkout_url": checkout_url,
                "order_id": order_id,
            }

    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        logger.exception(e)
        return {
            "success": False,
            "reason": "exception",
            "message": f"Error: {str(e)}",
        }


async def verify_payment_status(
    payment_link_id: str,
    contract_id: int,
    user: User,
    db: Session,
) -> dict[str, Any]:
    """
    Verify payment status from Square API

    This is called from the redirect endpoint to verify that payment
    was actually completed before showing success page.
    Never trust query parameters alone - always verify server-side.

    Args:
        payment_link_id: Square payment link ID
        contract_id: Internal contract ID
        user: The provider
        db: Database session

    Returns:
        Dict with payment status and details
    """
    try:
        # Get Square integration
        square_integration = (
            db.query(SquareIntegration)
            .filter(
                SquareIntegration.user_id == user.firebase_uid,
                SquareIntegration.is_active == True,
            )
            .first()
        )

        if not square_integration:
            return {
                "success": False,
                "reason": "square_not_connected",
                "message": "Square integration not connected",
            }

        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)

        # Retrieve payment link to get order ID
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            payment_link_response = await http_client.get(
                f"{SQUARE_API_URL}/online-checkout/payment-links/{payment_link_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-12-18",
                },
            )

            if payment_link_response.status_code != 200:
                error_text = payment_link_response.text
                logger.error(f"Failed to retrieve payment link: {error_text}")
                return {
                    "success": False,
                    "reason": "payment_link_not_found",
                    "message": "Payment link not found",
                }

            payment_link_data = payment_link_response.json()
            payment_link = payment_link_data.get("payment_link", {})
            order_id = payment_link.get("order_id")

            if not order_id:
                return {
                    "success": False,
                    "reason": "order_not_found",
                    "message": "Order not found",
                }

            # Retrieve order to check payment status
            order_response = await http_client.get(
                f"{SQUARE_API_URL}/orders/{order_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-12-18",
                },
            )

            if order_response.status_code != 200:
                error_text = order_response.text
                logger.error(f"Failed to retrieve order: {error_text}")
                return {
                    "success": False,
                    "reason": "order_retrieval_failed",
                    "message": "Failed to retrieve order",
                }

            order_data = order_response.json()
            order = order_data.get("order", {})

            # Check if order has payments
            tenders = order.get("tenders", [])
            if not tenders:
                return {
                    "success": False,
                    "paid": False,
                    "reason": "no_payment",
                    "message": "No payment found for this order",
                }

            # Check if any tender is completed
            completed_payment = None
            for tender in tenders:
                if (
                    tender.get("type") == "CARD"
                    and tender.get("card_details", {}).get("status") == "CAPTURED"
                ):
                    completed_payment = tender
                    break

            if not completed_payment:
                return {
                    "success": False,
                    "paid": False,
                    "reason": "payment_not_completed",
                    "message": "Payment not completed",
                }

            # Payment is verified as completed
            payment_id = completed_payment.get("id")
            amount_money = completed_payment.get("amount_money", {})
            amount = amount_money.get("amount", 0) / 100  # Convert from cents

            logger.info(f"✅ Payment verified for contract {contract_id}: {payment_id} - ${amount}")

            return {
                "success": True,
                "paid": True,
                "payment_id": payment_id,
                "amount": amount,
                "currency": amount_money.get("currency", "USD"),
                "order_id": order_id,
            }

    except Exception as e:
        logger.error(f"Error verifying payment status: {str(e)}")
        logger.exception(e)
        return {
            "success": False,
            "reason": "exception",
            "message": f"Error: {str(e)}",
        }


async def get_order_metadata(
    order_id: str,
    user: User,
    db: Session,
) -> dict[str, Any]:
    """
    Retrieve order metadata from Square API

    Used by webhook handler to match orders to contracts.

    Args:
        order_id: Square order ID
        user: The provider
        db: Database session

    Returns:
        Dict with order metadata including contract_id
    """
    try:
        # Get Square integration
        square_integration = (
            db.query(SquareIntegration)
            .filter(
                SquareIntegration.user_id == user.firebase_uid,
                SquareIntegration.is_active == True,
            )
            .first()
        )

        if not square_integration:
            return {
                "success": False,
                "reason": "square_not_connected",
            }

        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)

        # Retrieve order
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            order_response = await http_client.get(
                f"{SQUARE_API_URL}/orders/{order_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-12-18",
                },
            )

            if order_response.status_code != 200:
                error_text = order_response.text
                logger.error(f"Failed to retrieve order: {error_text}")
                return {
                    "success": False,
                    "reason": "order_retrieval_failed",
                }

            order_data = order_response.json()
            order = order_data.get("order", {})
            metadata = order.get("metadata", {})

            return {
                "success": True,
                "metadata": metadata,
                "order": order,
            }

    except Exception as e:
        logger.error(f"Error retrieving order metadata: {str(e)}")
        logger.exception(e)
        return {
            "success": False,
            "reason": "exception",
            "message": f"Error: {str(e)}",
        }


async def find_contract_by_order(
    order_id: str,
    db: Session,
) -> Optional[Contract]:
    """
    Find contract associated with a Square order

    Uses order metadata to match the order to a contract.
    This is used by the webhook handler.

    Args:
        order_id: Square order ID
        db: Database session

    Returns:
        Contract if found, None otherwise
    """
    try:
        # First, try to find any user with Square integration to query the order
        square_integration = (
            db.query(SquareIntegration).filter(SquareIntegration.is_active == True).first()
        )

        if not square_integration:
            logger.warning("No active Square integration found")
            return None

        # Get user
        user = db.query(User).filter(User.firebase_uid == square_integration.user_id).first()
        if not user:
            logger.warning(f"User not found for Square integration: {square_integration.user_id}")
            return None

        # Get order metadata
        order_result = await get_order_metadata(order_id, user, db)

        if not order_result.get("success"):
            logger.warning(f"Failed to get order metadata: {order_result.get('reason')}")
            return None

        metadata = order_result.get("metadata", {})
        contract_id = metadata.get("contract_id")

        if not contract_id:
            logger.warning(f"No contract_id in order metadata for order {order_id}")
            return None

        # Find contract by ID
        contract = db.query(Contract).filter(Contract.id == int(contract_id)).first()

        if contract:
            logger.info(f"✅ Found contract {contract.id} for order {order_id}")
        else:
            logger.warning(f"Contract {contract_id} not found for order {order_id}")

        return contract

    except Exception as e:
        logger.error(f"Error finding contract by order: {str(e)}")
        logger.exception(e)
        return None
