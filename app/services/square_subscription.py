"""
Square Subscription Service
Handles automatic Square subscription creation for recurring services
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from ..config import SECRET_KEY
from ..models import Client, Contract, User
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


def get_subscription_cadence(frequency: str) -> str:
    """
    Map service frequency to Square subscription cadence

    Args:
        frequency: Service frequency (weekly, bi-weekly, monthly, etc.)

    Returns:
        Square cadence: WEEKLY, EVERY_TWO_WEEKS, MONTHLY, etc.
    """
    frequency_map = {
        "weekly": "WEEKLY",
        "bi-weekly": "EVERY_TWO_WEEKS",
        "biweekly": "EVERY_TWO_WEEKS",
        "every-two-weeks": "EVERY_TWO_WEEKS",
        "monthly": "MONTHLY",
        "quarterly": "QUARTERLY",
        "every-six-months": "EVERY_SIX_MONTHS",
        "annual": "ANNUAL",
        "yearly": "ANNUAL",
    }

    return frequency_map.get(frequency.lower(), "MONTHLY")


async def create_square_subscription(
    contract: Contract, client: Client, user: User, db: Session, card_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Create a Square subscription for recurring services after first payment

    Args:
        contract: The signed contract with payment info
        client: The client who will be charged
        user: The provider (business owner)
        db: Database session
        card_id: Square card ID from first payment (optional)

    Returns:
        Dict with success status, subscription_id, and details
    """
    try:
        # Check if this is a recurring service
        if not contract.frequency or contract.frequency.lower() in [
            "one-time",
            "per-turnover",
            "on-demand",
            "as-needed",
        ]:
            logger.info(f"Contract {contract.id} is not recurring, skipping subscription")
            return {
                "success": False,
                "reason": "not_recurring",
                "message": "Service is not recurring",
            }

        # Check if Square is connected
        square_integration = (
            db.query(SquareIntegration)
            .filter(SquareIntegration.user_id == user.firebase_uid, SquareIntegration.is_active)
            .first()
        )

        if not square_integration:
            logger.info(f"Square not connected for user {user.id}, skipping subscription")
            return {
                "success": False,
                "reason": "square_not_connected",
                "message": "Square integration not connected",
            }

        # Check if subscription already exists
        if contract.square_subscription_id:
            logger.info(
                f"Subscription already exists for contract {contract.id}: {contract.square_subscription_id}"
            )
            return {
                "success": False,
                "reason": "subscription_exists",
                "message": "Subscription already created",
                "subscription_id": contract.square_subscription_id,
            }

        # Check if first payment was successful
        if contract.square_payment_status != "paid":
            logger.info(
                f"First payment not completed for contract {contract.id}, cannot create subscription"
            )
            return {
                "success": False,
                "reason": "payment_not_completed",
                "message": "First payment must be completed before creating subscription",
            }

        # Decrypt access token
        access_token = decrypt_token(square_integration.access_token)

        # First, create or get Square customer
        customer_result = await _create_or_get_square_customer(
            client=client, access_token=access_token, merchant_id=square_integration.merchant_id
        )

        if not customer_result.get("success"):
            return customer_result

        customer_id = customer_result["customer_id"]

        # Create subscription plan if needed
        plan_result = await _create_subscription_plan(
            contract=contract, access_token=access_token, merchant_id=square_integration.merchant_id
        )

        if not plan_result.get("success"):
            return plan_result

        plan_id = plan_result["plan_id"]

        # Create subscription
        subscription_data = {
            "idempotency_key": f"sub-{contract.id}-{int(datetime.utcnow().timestamp())}",
            "location_id": square_integration.merchant_id,
            "plan_id": plan_id,
            "customer_id": customer_id,
            "start_date": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "card_id": card_id,
            "timezone": "America/New_York",
            "source": {"name": f"CleanEnroll - {contract.title}"},
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{SQUARE_API_URL}/subscriptions",
                json=subscription_data,
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"Square subscription creation failed: {error_detail}")
                return {
                    "success": False,
                    "reason": "api_error",
                    "message": f"Square API error: {error_detail}",
                    "status_code": response.status_code,
                }

            subscription_response = response.json()
            subscription = subscription_response.get("subscription", {})

            subscription_id = subscription.get("id")
            status = subscription.get("status")

            if not subscription_id:
                logger.error(f"No subscription ID in Square response: {subscription_response}")
                return {
                    "success": False,
                    "reason": "invalid_response",
                    "message": "Invalid response from Square",
                }

            # Update contract with subscription details
            contract.square_subscription_id = subscription_id
            contract.square_subscription_status = status
            contract.square_subscription_created_at = datetime.utcnow()

            # Update client with subscription info
            client.square_subscription_id = subscription_id
            client.subscription_status = status
            client.subscription_frequency = contract.frequency

            db.commit()

            logger.info(
                f"✅ Square subscription created successfully: {subscription_id} for contract {contract.id}"
            )

            return {
                "success": True,
                "subscription_id": subscription_id,
                "status": status,
                "message": "Square subscription created successfully",
            }

    except Exception as e:
        logger.error(f"Error creating Square subscription for contract {contract.id}: {str(e)}")
        db.rollback()
        return {"success": False, "reason": "exception", "message": f"Error: {str(e)}"}


async def _create_or_get_square_customer(
    client: Client, access_token: str, merchant_id: str
) -> dict[str, Any]:
    """
    Create or retrieve Square customer for the client
    """
    try:
        # Check if customer already exists by email
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Search for existing customer
            search_response = await http_client.post(
                f"{SQUARE_API_URL}/customers/search",
                json={"query": {"filter": {"email_address": {"exact": client.email}}}},
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if search_response.status_code == 200:
                search_data = search_response.json()
                customers = search_data.get("customers", [])
                if customers:
                    customer_id = customers[0]["id"]
                    logger.info(f"Found existing Square customer: {customer_id}")
                    return {"success": True, "customer_id": customer_id}

            # Create new customer
            customer_data = {
                "idempotency_key": f"cust-{client.id}-{int(datetime.utcnow().timestamp())}",
                "given_name": client.contact_name or client.business_name,
                "email_address": client.email,
                "phone_number": client.phone if client.phone else None,
                "company_name": client.business_name if client.contact_name else None,
                "reference_id": f"client-{client.id}",
            }

            # Remove None values
            customer_data = {k: v for k, v in customer_data.items() if v is not None}

            create_response = await http_client.post(
                f"{SQUARE_API_URL}/customers",
                json=customer_data,
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if create_response.status_code not in [200, 201]:
                error_detail = create_response.text
                logger.error(f"Failed to create Square customer: {error_detail}")
                return {
                    "success": False,
                    "reason": "customer_creation_failed",
                    "message": f"Failed to create customer: {error_detail}",
                }

            customer_response = create_response.json()
            customer = customer_response.get("customer", {})
            customer_id = customer.get("id")

            logger.info(f"✅ Created new Square customer: {customer_id}")

            return {"success": True, "customer_id": customer_id}

    except Exception as e:
        logger.error(f"Error creating/getting Square customer: {str(e)}")
        return {"success": False, "reason": "exception", "message": f"Error: {str(e)}"}


async def _create_subscription_plan(
    contract: Contract, access_token: str, merchant_id: str
) -> dict[str, Any]:
    """
    Create a subscription plan for the contract
    """
    try:
        cadence = get_subscription_cadence(contract.frequency)

        plan_data = {
            "idempotency_key": f"plan-{contract.id}-{int(datetime.utcnow().timestamp())}",
            "subscription_plan": {
                "name": f"{contract.title} - {contract.frequency}",
                "phases": [
                    {
                        "cadence": cadence,
                        "recurring_price_money": {
                            "amount": int(contract.total_value * 100),  # Convert to cents
                            "currency": contract.currency or "USD",
                        },
                        "ordinal": 0,
                    }
                ],
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{SQUARE_API_URL}/catalog/object",
                json=plan_data,
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"Failed to create subscription plan: {error_detail}")
                return {
                    "success": False,
                    "reason": "plan_creation_failed",
                    "message": f"Failed to create plan: {error_detail}",
                }

            plan_response = response.json()
            catalog_object = plan_response.get("catalog_object", {})
            plan_id = catalog_object.get("id")

            logger.info(f"✅ Created subscription plan: {plan_id}")

            return {"success": True, "plan_id": plan_id}

    except Exception as e:
        logger.error(f"Error creating subscription plan: {str(e)}")
        return {"success": False, "reason": "exception", "message": f"Error: {str(e)}"}


async def cancel_square_subscription(
    subscription_id: str, user: User, db: Session
) -> dict[str, Any]:
    """
    Cancel a Square subscription
    """
    try:
        square_integration = (
            db.query(SquareIntegration)
            .filter(SquareIntegration.user_id == user.firebase_uid, SquareIntegration.is_active)
            .first()
        )

        if not square_integration:
            return {
                "success": False,
                "reason": "square_not_connected",
                "message": "Square integration not connected",
            }

        access_token = decrypt_token(square_integration.access_token)

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{SQUARE_API_URL}/subscriptions/{subscription_id}/cancel",
                headers={
                    "Square-Version": "2024-12-18",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"Failed to cancel subscription: {error_detail}")
                return {
                    "success": False,
                    "reason": "api_error",
                    "message": f"Square API error: {error_detail}",
                }

            logger.info(f"✅ Cancelled Square subscription: {subscription_id}")

            return {"success": True, "message": "Subscription cancelled successfully"}

    except Exception as e:
        logger.error(f"Error cancelling subscription {subscription_id}: {str(e)}")
        return {"success": False, "reason": "exception", "message": f"Error: {str(e)}"}
