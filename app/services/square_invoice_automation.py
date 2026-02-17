"""
Square Invoice Automation
Automatically creates and sends Square invoices after both parties sign the contract
"""

import logging
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from ..email_service import send_email
from ..models import BusinessConfig, Client, Contract, User
from ..models_square import SquareIntegration

logger = logging.getLogger(__name__)

SQUARE_API_URL = "https://connect.squareup.com/v2"


async def should_send_square_invoice(contract: Contract, user: User, db: Session) -> bool:
    """
    Check if Square invoice should be auto-sent for this contract
    """
    # Check if Square is connected
    square_integration = (
        db.query(SquareIntegration)
        .filter(SquareIntegration.user_id == user.firebase_uid, SquareIntegration.is_active)
        .first()
    )

    if not square_integration:
        logger.info(f"Square not connected for user {user.id}, skipping auto-invoice")
        return False

    # Check if invoice already sent
    if contract.invoice_auto_sent or contract.square_invoice_id:
        logger.info(f"Invoice already sent for contract {contract.id}")
        return False

    # Check if both parties signed
    if not (contract.client_signature and contract.provider_signed_at):
        logger.info(f"Contract {contract.id} not fully signed yet")
        return False

    return True


async def auto_send_square_invoice(contract: Contract, user: User, db: Session):
    """
    Automatically create and send Square invoice after both parties sign
    """
    try:
        logger.info(f"🔄 Starting auto-invoice for contract {contract.id}")

        # Get Square integration
        square_integration = (
            db.query(SquareIntegration)
            .filter(SquareIntegration.user_id == user.firebase_uid, SquareIntegration.is_active)
            .first()
        )

        if not square_integration:
            logger.warning(f"Square integration not found for user {user.id}")
            return

        # Get client
        client = db.query(Client).filter(Client.id == contract.client_id).first()
        if not client:
            logger.error(f"Client not found for contract {contract.id}")
            return

        # Create Square invoice
        invoice = await create_square_invoice(
            square_integration=square_integration, contract=contract, client=client
        )

        # Update contract
        contract.square_invoice_id = invoice["id"]
        contract.square_invoice_url = invoice.get("public_url", "")
        contract.invoice_auto_sent = True
        contract.invoice_auto_sent_at = datetime.utcnow()
        contract.square_payment_status = "pending"

        db.commit()

        # Send email to client
        await send_invoice_ready_email(client, contract, user, db)

        logger.info(f"✅ Auto-sent Square invoice for contract {contract.id}: {invoice['id']}")

    except Exception as e:
        logger.error(f"❌ Failed to auto-send invoice for contract {contract.id}: {str(e)}")
        logger.exception(e)
        # Don't raise - log and continue


async def create_square_invoice(
    square_integration: SquareIntegration, contract: Contract, client: Client
) -> dict:
    """Create Square invoice for contract"""
    from ..security_utils import decrypt_token

    access_token = decrypt_token(square_integration.access_token)

    # Build invoice payload
    invoice_payload = {
        "invoice": {
            "location_id": square_integration.merchant_id,
            "order_id": None,  # Will be created
            "primary_recipient": {
                "customer_id": (
                    client.square_customer_id
                    if hasattr(client, "square_customer_id") and client.square_customer_id
                    else None
                ),
                "given_name": client.contact_name or client.business_name,
                "email_address": client.email,
                "phone_number": client.phone,
            },
            "payment_requests": [
                {
                    "request_type": "BALANCE",
                    "due_date": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "automatic_payment_source": "NONE",
                }
            ],
            "delivery_method": "EMAIL",
            "invoice_number": f"INV-{contract.public_id[:8].upper()}",
            "title": contract.title,
            "description": contract.description or "Cleaning service",
            "scheduled_at": datetime.utcnow().isoformat(),
        },
        "idempotency_key": str(uuid.uuid4()),
    }

    # Create order with line items
    order_payload = {
        "order": {
            "location_id": square_integration.merchant_id,
            "line_items": [
                {
                    "name": contract.title,
                    "quantity": "1",
                    "base_price_money": {
                        "amount": int(contract.total_value * 100),  # Convert to cents
                        "currency": "USD",
                    },
                }
            ],
        },
        "idempotency_key": str(uuid.uuid4()),
    }

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        # Create order first
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
            raise Exception(f"Failed to create order: {error_text}")

        order = order_response.json()["order"]
        invoice_payload["invoice"]["order_id"] = order["id"]

        # Create invoice
        logger.info(f"Creating Square invoice for contract {contract.id}")
        invoice_response = await http_client.post(
            f"{SQUARE_API_URL}/invoices",
            json=invoice_payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Square-Version": "2024-12-18",
            },
        )

        if invoice_response.status_code != 200:
            error_text = invoice_response.text
            logger.error(f"Failed to create Square invoice: {error_text}")
            raise Exception(f"Failed to create invoice: {error_text}")

        invoice = invoice_response.json()["invoice"]

        # Publish invoice (sends email)
        logger.info(f"Publishing Square invoice {invoice['id']}")
        publish_response = await http_client.post(
            f"{SQUARE_API_URL}/invoices/{invoice['id']}/publish",
            json={"version": invoice["version"], "idempotency_key": str(uuid.uuid4())},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Square-Version": "2024-12-18",
            },
        )

        if publish_response.status_code != 200:
            error_text = publish_response.text
            logger.error(f"Failed to publish Square invoice: {error_text}")
            raise Exception(f"Failed to publish invoice: {error_text}")

        published_invoice = publish_response.json()["invoice"]
        logger.info(f"✅ Square invoice published: {published_invoice['id']}")

        return published_invoice


async def send_invoice_ready_email(client: Client, contract: Contract, user: User, db: Session):
    """Send email to client when invoice is ready"""
    try:
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        business_name = business_config.business_name if business_config else "Service Provider"
        client_name = client.contact_name or client.business_name

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Invoice Ready! 💳</h1>
            </div>

            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                    Hi {client_name},
                </p>

                <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                    Great news! Your service is confirmed and your invoice is ready for payment.
                </p>

                <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #10b981;">
                    <h2 style="color: #10b981; font-size: 20px; margin-top: 0; margin-bottom: 15px;">
                        Invoice Details
                    </h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Service:</td>
                            <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.title}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Amount:</td>
                            <td style="padding: 8px 0; color: #10b981; font-weight: bold; font-size: 20px; text-align: right;">
                                ${contract.total_value:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Due Date:</td>
                            <td style="padding: 8px 0; color: #1e293b; text-align: right;">
                                {(datetime.utcnow() + timedelta(days=7)).strftime('%B %d, %Y')}
                            </td>
                        </tr>
                    </table>
                </div>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{contract.square_invoice_url}"
                       style="display: inline-block; background: #10b981; color: white; padding: 16px 32px;
                              text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 18px; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);">
                        Pay Invoice Now →
                    </a>
                </div>

                <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                    <p style="margin: 0; color: #1e40af; font-size: 14px;">
                        <strong>💳 Secure Payment:</strong> Your payment is processed securely through Square.
                        You can pay with credit card, debit card, or other accepted payment methods.
                    </p>
                </div>

                <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                    Questions about your invoice? Contact {business_name} directly.
                </p>
            </div>
        </div>
        """

        if client.email:
            from ..email_templates import invoice_ready_template

            invoice_number = (
                f"INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}"
            )
            due_date = (datetime.utcnow() + timedelta(days=7)).strftime("%B %d, %Y")

            mjml_content = invoice_ready_template(
                client_name=client_name,
                business_name=business_name,
                invoice_number=invoice_number,
                amount=contract.total_value,
                due_date=due_date,
                payment_url=contract.square_invoice_url,
            )

            await send_email(
                to=client.email,
                subject=f"Invoice Ready - {contract.title}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(f"✅ Invoice ready email sent to {client.email}")

    except Exception as e:
        logger.error(f"❌ Failed to send invoice ready email: {str(e)}")
