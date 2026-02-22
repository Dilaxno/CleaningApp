"""
Square Webhook Handler
Handles payment completion and triggers subscription creation
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, SQUARE_WEBHOOK_SIGNATURE_KEY
from ..database import get_db
from ..email_service import send_email
from ..email_templates import THEME
from ..models import Client, Contract, User
from ..services.square_subscription import create_square_subscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/square", tags=["webhooks"])


def verify_square_signature(body: bytes, signature: str, notification_url: str) -> bool:
    """
    Verify Square webhook signature
    https://developer.squareup.com/docs/webhooks/step3validate

    Square generates the signature using: HMAC-SHA256(signature_key, notification_url + request_body)
    """
    if not SQUARE_WEBHOOK_SIGNATURE_KEY:
        logger.warning("⚠️ SQUARE_WEBHOOK_SIGNATURE_KEY not configured, skipping verification")
        return True  # Allow in development

    try:
        # Concatenate notification_url + request_body (this is the message to sign)
        message = notification_url.encode("utf-8") + body

        # Compute HMAC-SHA256 signature using the signature_key
        computed_signature = hmac.new(
            SQUARE_WEBHOOK_SIGNATURE_KEY.encode("utf-8"), message, hashlib.sha256
        ).digest()

        # Convert to base64 (Square sends signature in base64 format)
        import base64

        computed_signature_b64 = base64.b64encode(computed_signature).decode("utf-8")

        # Compare signatures (use compare_digest to prevent timing attacks)
        is_valid = hmac.compare_digest(computed_signature_b64, signature)

        if not is_valid:
            logger.warning(
                f"⚠️ Signature mismatch - Expected: {computed_signature_b64[:20]}..., Got: {signature[:20]}..."
            )

        return is_valid
    except Exception as e:
        logger.error(f"❌ Signature verification failed: {e}")
        return False


@router.post("/payment")
async def handle_square_payment_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Square payment webhook events

    Events handled:
    - invoice.payment_made - Invoice paid successfully
    - payment.created - Payment created
    - payment.updated - Payment status updated

    Actions:
    1. Update contract payment status
    2. Create subscription for recurring services
    3. Send confirmation emails
    """
    try:
        # Get request body and signature
        body = await request.body()
        signature = request.headers.get("x-square-hmacsha256-signature", "")

        # Get the full notification URL (this is required for signature verification)
        notification_url = str(request.url)

        # Verify webhook signature
        if not verify_square_signature(body, signature, notification_url):
            logger.error("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse webhook payload
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error("❌ Invalid JSON payload")
            raise HTTPException(status_code=400, detail="Invalid JSON") from None

        event_type = payload.get("type")
        event_data = payload.get("data", {})

        logger.info(f"📥 Received Square webhook: {event_type}")

        # Handle invoice payment events
        if event_type == "invoice.payment_made":
            await handle_invoice_payment(event_data, db)

        # Handle payment events
        elif event_type in ["payment.created", "payment.updated"]:
            await handle_payment_event(event_data, db)

        else:
            logger.info(f"ℹ️ Unhandled event type: {event_type}")

        return {"status": "success", "event_type": event_type}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def handle_invoice_payment(event_data: dict, db: Session):
    """
    Handle invoice.payment_made event
    Triggered when an invoice is paid
    """
    try:
        invoice_data = event_data.get("object", {}).get("invoice", {})
        invoice_id = invoice_data.get("id")
        payment_status = invoice_data.get("status", "").lower()

        if not invoice_id:
            logger.warning("⚠️ No invoice ID in webhook payload")
            return

        logger.info(f"💰 Invoice payment event: {invoice_id} - Status: {payment_status}")

        # Find contract by Square invoice ID
        contract = db.query(Contract).filter(Contract.square_invoice_id == invoice_id).first()

        if not contract:
            logger.warning(f"⚠️ No contract found for Square invoice: {invoice_id}")
            return

        # Update payment status
        old_status = contract.square_payment_status

        if payment_status == "paid":
            contract.square_payment_status = "paid"
            contract.square_payment_received_at = datetime.utcnow()

            # Update contract status to active if not already
            if contract.status == "signed":
                contract.status = "active"

            db.commit()

            logger.info(f"✅ Contract {contract.id} payment status updated: {old_status} → paid")

            # Get related data
            client = db.query(Client).filter(Client.id == contract.client_id).first()
            user = db.query(User).filter(User.id == contract.user_id).first()

            if not client or not user:
                logger.error(f"❌ Missing client or user for contract {contract.id}")
                return

            # Create subscription for recurring services
            if contract.frequency and contract.frequency.lower() not in [
                "one-time",
                "per-turnover",
                "on-demand",
                "as-needed",
            ]:
                logger.info(f"🔄 Creating subscription for recurring service: {contract.frequency}")

                subscription_result = await create_square_subscription(
                    contract=contract,
                    client=client,
                    user=user,
                    db=db,
                    card_id=None,  # Square will use the card from the invoice payment
                )

                if subscription_result.get("success"):
                    subscription_id = subscription_result["subscription_id"]
                    logger.info(f"✅ Subscription created: {subscription_id}")

                    # Send subscription confirmation email to CLIENT
                    await send_subscription_confirmation_email(
                        client=client, contract=contract, subscription_id=subscription_id, user=user
                    )

                    # Send subscription notification to OWNER
                    await send_subscription_notification_to_owner(
                        client=client, contract=contract, subscription_id=subscription_id, user=user
                    )
                else:
                    logger.error(
                        f"❌ Subscription creation failed: {subscription_result.get('message')}"
                    )

            # Send payment confirmation email
            await send_payment_confirmation_email(client=client, contract=contract, user=user)

        elif payment_status in ["canceled", "cancelled"]:
            contract.square_payment_status = "cancelled"
            db.commit()
            logger.info(f"⚠️ Contract {contract.id} payment cancelled")

        elif payment_status == "failed":
            contract.square_payment_status = "failed"
            db.commit()
            logger.info(f"❌ Contract {contract.id} payment failed")

    except Exception as e:
        logger.error(f"❌ Error handling invoice payment: {str(e)}")
        db.rollback()


async def handle_payment_event(event_data: dict, db: Session):
    """
    Handle payment.created and payment.updated events
    Tracks payment status and triggers confirmation flow

    This is the source of truth for payment confirmation.
    The redirect endpoint provides immediate UX feedback, but this webhook
    handles all the actual database updates and notifications.
    """
    try:
        payment_data = event_data.get("object", {}).get("payment", {})
        payment_id = payment_data.get("id")
        status = payment_data.get("status", "").upper()
        order_id = payment_data.get("order_id")

        logger.info(f"💳 Payment event: {payment_id} - Status: {status} - Order: {order_id}")

        # Only process COMPLETED payments
        if status != "COMPLETED":
            logger.info(f"ℹ️ Payment {payment_id} status is {status}, not COMPLETED. Skipping.")
            return

        if not order_id:
            logger.warning(f"⚠️ No order_id in payment {payment_id}")
            return

        # Find contract using order metadata
        from ..services.square_service import find_contract_by_order

        contract = await find_contract_by_order(order_id, db)

        if not contract:
            logger.warning(f"⚠️ No contract found for payment {payment_id} (order: {order_id})")
            return

        # Get related data
        client = db.query(Client).filter(Client.id == contract.client_id).first()
        user = db.query(User).filter(User.id == contract.user_id).first()

        if not client or not user:
            logger.error(f"❌ Missing client or user for contract {contract.id}")
            return

        # Update payment status
        old_status = contract.square_payment_status
        contract.square_payment_status = "paid"
        contract.square_payment_received_at = datetime.utcnow()

        # Update contract status to active if not already
        if contract.status == "signed":
            contract.status = "active"

        # Store payment confirmation state for frontend redirect
        # This allows the frontend to detect successful payment and redirect
        contract.payment_confirmation_pending = True
        contract.payment_confirmed_at = datetime.utcnow()

        db.commit()
        db.refresh(contract)

        logger.info(f"✅ Contract {contract.id} payment status updated: {old_status} → paid")
        logger.info("✅ Payment confirmation state stored for frontend redirect")

        # Send payment confirmation email to service provider
        await send_provider_payment_notification(
            client=client, contract=contract, user=user, payment_id=payment_id
        )

        # Create subscription for recurring services
        if contract.frequency and contract.frequency.lower() not in [
            "one-time",
            "per-turnover",
            "on-demand",
            "as-needed",
        ]:
            logger.info(f"🔄 Creating subscription for recurring service: {contract.frequency}")

            subscription_result = await create_square_subscription(
                contract=contract,
                client=client,
                user=user,
                db=db,
                card_id=None,  # Square will use the card from the payment
            )

            if subscription_result.get("success"):
                subscription_id = subscription_result["subscription_id"]
                logger.info(f"✅ Subscription created: {subscription_id}")

                # Send subscription confirmation email to CLIENT
                await send_subscription_confirmation_email(
                    client=client, contract=contract, subscription_id=subscription_id, user=user
                )

                # Send subscription notification to OWNER
                await send_subscription_notification_to_owner(
                    client=client, contract=contract, subscription_id=subscription_id, user=user
                )
            else:
                logger.error(
                    f"❌ Subscription creation failed: {subscription_result.get('message')}"
                )

        # Send payment confirmation email to client
        await send_payment_confirmation_email(client=client, contract=contract, user=user)

        # Send SMS notification to client if Twilio is enabled
        if client.phone:
            try:
                from ..services.twilio_service import send_payment_confirmation_sms

                # Generate invoice number from contract
                invoice_number = (
                    f"CLN-{contract.public_id[:8].upper()}"
                    if contract.public_id
                    else f"#{contract.id}"
                )

                await send_payment_confirmation_sms(
                    db=db,
                    user_id=user.id,
                    client_phone=client.phone,
                    client_name=client.contact_name or client.business_name,
                    amount=contract.total_value or 0.0,
                    invoice_number=invoice_number,
                )
            except Exception as e:
                logger.error(f"Failed to send payment SMS notification: {e}")

    except Exception as e:
        logger.error(f"❌ Error handling payment event: {str(e)}")
        db.rollback()


async def send_payment_confirmation_email(client: Client, contract: Contract, user: User):
    """Send payment confirmation email to client and owner"""
    try:
        from ..models import BusinessConfig

        # Get business config for branding
        db = next(get_db())
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        business_name = business_config.business_name if business_config else "CleanEnroll"

        # Check if this is a recurring service
        is_recurring = contract.frequency and contract.frequency.lower() not in [
            "one-time",
            "per-turnover",
            "on-demand",
            "as-needed",
        ]

        # Email to client
        if client.email:
            subscription_note = ""
            if is_recurring:
                subscription_note = f"""
                <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 16px; padding: 20px; margin: 24px 0; border: 1px solid #a7f3d0;">
                    <table cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                            <td style="width: 48px; vertical-align: top; padding-right: 16px;">
                                <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
                                    <span style="font-size: 24px;">🔄</span>
                                </div>
                            </td>
                            <td style="vertical-align: top;">
                                <h3 style="margin: 0 0 8px 0; color: #065f46; font-size: 18px; font-weight: 700;">
                                    Recurring Service Active
                                </h3>
                                <p style="margin: 0; color: #047857; font-size: 15px; line-height: 1.6;">
                                    Your {contract.frequency} subscription is now active! You'll receive automatic invoices and service reminders.
                                </p>
                            </td>
                        </tr>
                    </table>
                </div>
                """

            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="X-UA-Compatible" content="IE=edge">
                <title>Payment Received</title>
                <!--[if mso]>
                <style type="text/css">
                    body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
                </style>
                <![endif]-->
            </head>
            <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f8fafc; padding: 20px 0;">
                    <tr>
                        <td align="center">
                            <!-- Main Container -->
                            <table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);">

                                <!-- Header -->
                                <tr>
                                    <td style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 40px 30px; text-align: center;">
                                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                            <tr>
                                                <td align="center">
                                                    <!-- Success Icon -->
                                                    <div style="width: 80px; height: 80px; background-color: rgba(255, 255, 255, 0.2); border-radius: 50%; display: inline-flex; align-items: center; justify-center; margin-bottom: 20px; backdrop-filter: blur(10px);">
                                                        <span style="font-size: 40px; line-height: 1;">✅</span>
                                                    </div>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td align="center">
                                                    <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">
                                                        Payment Received!
                                                    </h1>
                                                    <p style="margin: 12px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 16px; font-weight: 400;">
                                                        Thank you for your payment
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <!-- Body Content -->
                                <tr>
                                    <td style="padding: 40px 30px;">
                                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                            <!-- Greeting -->
                                            <tr>
                                                <td style="padding-bottom: 24px;">
                                                    <p style="margin: 0; font-size: 17px; color: #1e293b; line-height: 1.6;">
                                                        Hi <strong>{client.contact_name or client.business_name}</strong>,
                                                    </p>
                                                </td>
                                            </tr>

                                            <!-- Message -->
                                            <tr>
                                                <td style="padding-bottom: 32px;">
                                                    <p style="margin: 0; font-size: 16px; color: #475569; line-height: 1.7;">
                                                        We've successfully received your payment for <strong style="color: #1e293b;">{contract.title}</strong>. Your service is now confirmed!
                                                    </p>
                                                </td>
                                            </tr>

                                            <!-- Payment Details Card -->
                                            <tr>
                                                <td style="padding-bottom: 32px;">
                                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden;">
                                                        <!-- Card Header -->
                                                        <tr>
                                                            <td style="padding: 24px 24px 20px 24px;">
                                                                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                    <tr>
                                                                        <td style="width: 40px; vertical-align: middle; padding-right: 12px;">
                                                                            <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                                                                                <span style="font-size: 20px;">💳</span>
                                                                            </div>
                                                                        </td>
                                                                        <td style="vertical-align: middle;">
                                                                            <h2 style="margin: 0; color: #0f172a; font-size: 20px; font-weight: 700;">
                                                                                Payment Details
                                                                            </h2>
                                                                        </td>
                                                                    </tr>
                                                                </table>
                                                            </td>
                                                        </tr>

                                                        <!-- Card Content -->
                                                        <tr>
                                                            <td style="padding: 0 24px 24px 24px;">
                                                                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                    <!-- Invoice Number -->
                                                                    <tr>
                                                                        <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">
                                                                                        Invoice Number
                                                                                    </td>
                                                                                    <td align="right" style="color: #1e293b; font-size: 14px; font-weight: 600; font-family: 'Courier New', monospace;">
                                                                                        INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>

                                                                    <!-- Service -->
                                                                    <tr>
                                                                        <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">
                                                                                        Service
                                                                                    </td>
                                                                                    <td align="right" style="color: #1e293b; font-size: 14px; font-weight: 500;">
                                                                                        {contract.title}
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>

                                                                    <!-- Amount Paid -->
                                                                    <tr>
                                                                        <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">
                                                                                        Amount Paid
                                                                                    </td>
                                                                                    <td align="right" style="color: #00C4B4; font-size: 22px; font-weight: 700;">
                                                                                        ${contract.total_value:.2f}
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>

                                                                    <!-- Payment Date -->
                                                                    <tr>
                                                                        <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0;">
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">
                                                                                        Payment Date
                                                                                    </td>
                                                                                    <td align="right" style="color: #1e293b; font-size: 14px; font-weight: 500;">
                                                                                        {datetime.utcnow().strftime('%B %d, %Y')}
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>

                                                                    {f'''
                                                                    <!-- Service Frequency -->
                                                                    <tr>
                                                                        <td style="padding: 12px 0;">
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="color: #64748b; font-size: 14px; font-weight: 600;">
                                                                                        Service Frequency
                                                                                    </td>
                                                                                    <td align="right" style="color: #1e293b; font-size: 14px; font-weight: 500;">
                                                                                        {contract.frequency.title()}
                                                                                    </td>
                                                                                </tr>
                                                                            </table>
                                                                        </td>
                                                                    </tr>
                                                                    ''' if contract.frequency else ''}
                                                                </table>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>

                                            <!-- Subscription Note -->
                                            {subscription_note if is_recurring else ''}

                                            <!-- What's Next Section -->
                                            <tr>
                                                <td style="padding-bottom: 32px;">
                                                    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 16px; padding: 24px; border: 1px solid #a7f3d0;">
                                                        <tr>
                                                            <td>
                                                                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                    <tr>
                                                                        <td style="width: 40px; vertical-align: top; padding-right: 12px;">
                                                                            <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                                                                                <span style="font-size: 20px;">✨</span>
                                                                            </div>
                                                                        </td>
                                                                        <td style="vertical-align: top;">
                                                                            <h3 style="margin: 0 0 16px 0; color: #065f46; font-size: 18px; font-weight: 700;">
                                                                                What's Next?
                                                                            </h3>
                                                                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                                                                <tr>
                                                                                    <td style="padding: 6px 0;">
                                                                                        <table cellpadding="0" cellspacing="0" border="0">
                                                                                            <tr>
                                                                                                <td style="width: 20px; vertical-align: top; padding-right: 8px;">
                                                                                                    <span style="color: #10b981; font-size: 16px;">✓</span>
                                                                                                </td>
                                                                                                <td style="color: #047857; font-size: 15px; line-height: 1.6;">
                                                                                                    Your service is confirmed and scheduled
                                                                                                </td>
                                                                                            </tr>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td style="padding: 6px 0;">
                                                                                        <table cellpadding="0" cellspacing="0" border="0">
                                                                                            <tr>
                                                                                                <td style="width: 20px; vertical-align: top; padding-right: 8px;">
                                                                                                    <span style="color: #10b981; font-size: 16px;">✓</span>
                                                                                                </td>
                                                                                                <td style="color: #047857; font-size: 15px; line-height: 1.6;">
                                                                                                    You'll receive a reminder before your appointment
                                                                                                </td>
                                                                                            </tr>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td style="padding: 6px 0;">
                                                                                        <table cellpadding="0" cellspacing="0" border="0">
                                                                                            <tr>
                                                                                                <td style="width: 20px; vertical-align: top; padding-right: 8px;">
                                                                                                    <span style="color: #10b981; font-size: 16px;">✓</span>
                                                                                                </td>
                                                                                                <td style="color: #047857; font-size: 15px; line-height: 1.6;">
                                                                                                    A receipt has been sent to your email
                                                                                                </td>
                                                                                            </tr>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                {f'''
                                                                                <tr>
                                                                                    <td style="padding: 6px 0;">
                                                                                        <table cellpadding="0" cellspacing="0" border="0">
                                                                                            <tr>
                                                                                                <td style="width: 20px; vertical-align: top; padding-right: 8px;">
                                                                                                    <span style="color: #10b981; font-size: 16px;">✓</span>
                                                                                                </td>
                                                                                                <td style="color: #047857; font-size: 15px; line-height: 1.6;">
                                                                                                    Your {contract.frequency} subscription is active
                                                                                                </td>
                                                                                            </tr>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                ''' if is_recurring else ''}
                                                                            </table>
                                                                        </td>
                                                                    </tr>
                                                                </table>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>

                                            <!-- Closing Message -->
                                            <tr>
                                                <td style="padding-bottom: 24px;">
                                                    <p style="margin: 0; font-size: 16px; color: #475569; line-height: 1.7;">
                                                        We look forward to serving you! If you have any questions, please don't hesitate to reach out.
                                                    </p>
                                                </td>
                                            </tr>

                                            <!-- Signature -->
                                            <tr>
                                                <td style="padding-top: 24px; border-top: 1px solid #e2e8f0;">
                                                    <p style="margin: 0 0 4px 0; font-size: 16px; color: #64748b;">
                                                        Best regards,
                                                    </p>
                                                    <p style="margin: 0; font-size: 18px; color: #1e293b; font-weight: 700;">
                                                        {business_name}
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <!-- Footer -->
                                <tr>
                                    <td style="background-color: #f8fafc; padding: 24px 30px; text-align: center; border-top: 1px solid #e2e8f0;">
                                        <p style="margin: 0; color: #94a3b8; font-size: 13px; line-height: 1.6;">
                                            This is an automated confirmation email. Please do not reply to this message.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """

            from ..email_templates import payment_confirmation_client_template

            payment_date = datetime.utcnow().strftime("%B %d, %Y")
            mjml_content = payment_confirmation_client_template(
                client_name=client.contact_name or client.business_name,
                business_name=business_name,
                amount=contract.total_value,
                contract_title=contract.title,
                payment_date=payment_date,
            )

            await send_email(
                to=client.email,
                subject=f"✅ Payment Received - {contract.title}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(f"✅ Payment confirmation email sent to client {client.email}")

        # Email to owner
        if user.email:
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">💰 Payment Received</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {user.full_name or 'there'},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        Great news! You've received a payment from <strong>{client.business_name}</strong>.
                    </p>

                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                        <h2 style="color: #00C4B4; font-size: 20px; margin-top: 0; margin-bottom: 15px;">
                            📋 Payment Details
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Invoice Number:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right; font-family: monospace;">
                                    INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Client:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">
                                    {client.contact_name or client.business_name}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Email:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.email}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Contract:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.title}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Amount:</td>
                                <td style="padding: 8px 0; color: #00C4B4; font-weight: bold; font-size: 18px; text-align: right;">
                                    ${contract.total_value:.2f}
                                </td>
                            </tr>
                            {f'<tr><td style="padding: 8px 0; color: #64748b; font-weight: 600;">Frequency:</td><td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.frequency.title()}</td></tr>' if contract.frequency else ''}
                        </table>
                    </div>

                    {f'<div style="background: #ecfdf5; border-left: 4px solid #00C4B4; padding: 15px; margin-bottom: 25px; border-radius: 4px;"><p style="margin: 0; color: #00C4B4; font-weight: 600;">🔄 Recurring Subscription Active</p><p style="margin: 8px 0 0 0; color: #1e293b; font-size: 14px;">This client is now on a {contract.frequency} subscription. Future payments will be processed automatically.</p></div>' if is_recurring else ''}

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 20px;">
                        The payment has been processed through Square and will be deposited according to your Square payout schedule.
                    </p>

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{FRONTEND_URL}/dashboard/contracts/{contract.public_id}"
                           style="display: inline-block; background: #00C4B4; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600;">
                            View Contract Details
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">

                    <p style="font-size: 14px; color: #1e293b; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>CleanEnroll</strong>
                    </p>
                </div>
            </div>
            """

            invoice_number = (
                f"INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}"
            )
            payment_date = datetime.utcnow().strftime("%B %d, %Y")

            mjml_content = payment_received_notification_template(
                provider_name=user.full_name or "there",
                client_name=client.contact_name or client.business_name,
                invoice_number=invoice_number,
                amount=contract.total_value,
                currency="USD",
                payment_date=payment_date,
            )

            await send_email(
                to=user.email,
                subject=f"💰 Payment Received - {client.business_name}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(f"✅ Payment confirmation email sent to owner {user.email}")

        logger.info(f"✅ Payment confirmation emails sent for contract {contract.id}")

    except Exception as e:
        logger.error(f"❌ Failed to send payment confirmation emails: {str(e)}")


async def send_subscription_confirmation_email(
    client: Client, contract: Contract, subscription_id: str, user: User
):
    """Send subscription confirmation email to client with detailed information"""
    try:
        from ..models import BusinessConfig

        db = next(get_db())
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        business_name = business_config.business_name if business_config else "CleanEnroll"

        # Calculate next billing date based on frequency
        next_billing_date = datetime.utcnow()
        if contract.frequency.lower() == "weekly":
            next_billing_date += timedelta(days=7)
        elif contract.frequency.lower() in ["bi-weekly", "biweekly", "every-two-weeks"]:
            next_billing_date += timedelta(days=14)
        elif contract.frequency.lower() == "monthly":
            next_billing_date += timedelta(days=30)
        elif contract.frequency.lower() == "quarterly":
            next_billing_date += timedelta(days=90)
        elif contract.frequency.lower() in ["annual", "yearly"]:
            next_billing_date += timedelta(days=365)

        next_billing_str = next_billing_date.strftime("%B %d, %Y")

        if client.email:
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">🎉 Subscription Activated!</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {client.contact_name or client.business_name},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        Great news! Your recurring service subscription has been successfully activated.
                        You're all set for hassle-free, automatic service scheduling and billing.
                    </p>

                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                        <h2 style="color: #00C4B4; font-size: 20px; margin-top: 0; margin-bottom: 15px;">
                            📋 Subscription Details
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Service:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.title}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Frequency:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.frequency.title()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Amount per Service:</td>
                                <td style="padding: 8px 0; color: #00C4B4; font-weight: bold; font-size: 18px; text-align: right;">
                                    ${contract.total_value:.2f}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Next Billing Date:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{next_billing_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Subscription ID:</td>
                                <td style="padding: 8px 0; color: #64748b; font-size: 12px; text-align: right;">{subscription_id}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="background: #ecfdf5; border-left: 4px solid #00C4B4; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <h3 style="color: #00C4B4; font-size: 16px; margin-top: 0; margin-bottom: 10px;">
                            ✅ What Happens Next?
                        </h3>
                        <ul style="margin: 0; padding-left: 20px; color: #1e293b;">
                            <li style="margin-bottom: 8px;">Your card will be automatically charged on the scheduled billing date</li>
                            <li style="margin-bottom: 8px;">You'll receive a notification 24 hours before each charge</li>
                            <li style="margin-bottom: 8px;">Services will be scheduled automatically based on your frequency</li>
                            <li style="margin-bottom: 8px;">You can manage, pause, or cancel anytime through your portal</li>
                        </ul>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{FRONTEND_URL}/client/subscription/{subscription_id}"
                           style="display: inline-block; background: #00C4B4; color: white; padding: 14px 30px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                            Manage Subscription
                        </a>
                    </div>

                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <p style="margin: 0; color: #92400e; font-size: 14px;">
                            <strong>💡 Pro Tip:</strong> You can pause your subscription anytime if you need to skip a service.
                            Just log in to your portal and click "Pause Subscription."
                        </p>
                    </div>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 10px;">
                        Thank you for choosing {business_name}! We're committed to providing you with excellent service.
                    </p>

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                        If you have any questions about your subscription, please don't hesitate to reach out.
                    </p>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>{business_name}</strong>
                    </p>
                </div>

                <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px;">
                    <p style="margin: 0;">
                        This is an automated confirmation email. Please do not reply to this message.
                    </p>
                </div>
            </div>
            """

            from ..email_templates import subscription_activated_template

            mjml_content = subscription_activated_template(
                client_name=client.contact_name or client.business_name,
                business_name=business_name,
                frequency=contract.frequency,
                contract_title=contract.title,
                amount=contract.total_value,
            )

            await send_email(
                to=client.email,
                subject=f"🎉 Subscription Activated - {contract.frequency.title()} {contract.title}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(
                f"✅ Subscription confirmation email sent to {client.email} for contract {contract.id}"
            )
        else:
            logger.warning(
                f"⚠️ No email address for client {client.id}, subscription confirmation not sent"
            )

    except Exception as e:
        logger.error(f"❌ Failed to send subscription confirmation email: {str(e)}")


async def send_subscription_notification_to_owner(
    client: Client, contract: Contract, subscription_id: str, user: User
):
    """Send subscription notification email to owner when subscription is created"""
    try:
        from ..models import BusinessConfig

        db = next(get_db())
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        # Business name available for future email customization

        # Calculate next billing date
        next_billing_date = datetime.utcnow()
        if contract.frequency.lower() == "weekly":
            next_billing_date += timedelta(days=7)
        elif contract.frequency.lower() in ["bi-weekly", "biweekly", "every-two-weeks"]:
            next_billing_date += timedelta(days=14)
        elif contract.frequency.lower() == "monthly":
            next_billing_date += timedelta(days=30)
        elif contract.frequency.lower() == "quarterly":
            next_billing_date += timedelta(days=90)
        elif contract.frequency.lower() in ["annual", "yearly"]:
            next_billing_date += timedelta(days=365)

        next_billing_str = next_billing_date.strftime("%B %d, %Y")

        if user.email:
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #00C4B4 0%, #00A89A 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">🔄 Subscription Created</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {user.full_name or 'there'},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        Great news! A recurring subscription has been successfully created for
                        <strong>{client.contact_name or client.business_name}</strong>.
                    </p>

                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                        <h2 style="color: #00C4B4; font-size: 20px; margin-top: 0; margin-bottom: 15px;">
                            📋 Subscription Details
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Client:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">
                                    {client.contact_name or client.business_name}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Email:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.email}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Service:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.title}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Frequency:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.frequency.title()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Amount per Service:</td>
                                <td style="padding: 8px 0; color: #00C4B4; font-weight: bold; font-size: 18px; text-align: right;">
                                    ${contract.total_value:.2f}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Next Billing Date:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{next_billing_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Subscription ID:</td>
                                <td style="padding: 8px 0; color: #64748b; font-size: 12px; text-align: right;">{subscription_id}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="background: #ecfdf5; border-left: 4px solid #00C4B4; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <h3 style="color: #00C4B4; font-size: 16px; margin-top: 0; margin-bottom: 10px;">
                            💰 Automatic Billing Active
                        </h3>
                        <ul style="margin: 0; padding-left: 20px; color: #1e293b;">
                            <li style="margin-bottom: 8px;">Client will be charged automatically on the billing schedule</li>
                            <li style="margin-bottom: 8px;">Payments will be deposited to your Square account</li>
                            <li style="margin-bottom: 8px;">Client can manage their subscription through their portal</li>
                            <li style="margin-bottom: 8px;">You'll receive notifications for each successful payment</li>
                        </ul>
                    </div>

                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <p style="margin: 0; color: #92400e; font-size: 14px;">
                            <strong>💡 Recurring Revenue:</strong> This subscription will generate
                            ${contract.total_value:.2f} {contract.frequency} automatically.
                            You can view all subscription details in your Square dashboard.
                        </p>
                    </div>

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{FRONTEND_URL}/dashboard/contracts/{contract.public_id}"
                           style="display: inline-block; background: #00C4B4; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600; margin-right: 10px;">
                            View Contract
                        </a>
                        <a href="https://squareup.com/dashboard/subscriptions"
                           style="display: inline-block; background: #64748b; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600;">
                            Square Dashboard
                        </a>
                    </div>

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                        The subscription is now active and will automatically charge the client according to the schedule.
                        All payments will be processed through Square and deposited to your account.
                    </p>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">

                    <p style="font-size: 14px; color: #1e293b; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>CleanEnroll</strong>
                    </p>
                </div>

                <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px;">
                    <p style="margin: 0;">
                        This is an automated notification. Manage subscriptions in your Square dashboard.
                    </p>
                </div>
            </div>
            """

            from ..email_templates import get_base_template

            content_sections = f"""
            <mj-text>
              Hi {user.full_name or 'there'},
            </mj-text>
            
            <mj-text>
              Great news! A new subscription has been created for <strong>{client.business_name}</strong>.
            </mj-text>
            
            <mj-text align="center" font-size="32px" font-weight="700" color="{THEME['success']}" padding="20px 0">
              ${contract.total_value:,.2f} / {contract.frequency}
            </mj-text>
            
            <mj-text font-size="14px" color="{THEME['text_muted']}">
              Client: {client.contact_name or client.business_name}<br/>
              Service: {contract.title}<br/>
              Frequency: {contract.frequency.title()}
            </mj-text>
            
            <mj-text font-size="14px" color="{THEME['text_muted']}" padding="20px 0 0 0">
              The subscription is now active and will automatically charge the client according to the schedule.
              All payments will be processed through Square and deposited to your account.
            </mj-text>
            """

            mjml_content = get_base_template(
                title="Subscription Created",
                preview_text=f"🔄 Subscription Created - {client.business_name} - {contract.frequency.title()}",
                content_sections=content_sections,
                cta_url=f"{FRONTEND_URL}/dashboard/contracts/{contract.public_id}",
                cta_label="View Contract",
                is_user_email=True,
            )

            await send_email(
                to=user.email,
                subject=f"🔄 Subscription Created - {client.business_name} - {contract.frequency.title()}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(
                f"✅ Subscription notification email sent to owner {user.email} for contract {contract.id}"
            )
        else:
            logger.warning(
                f"⚠️ No email address for owner {user.id}, subscription notification not sent"
            )

    except Exception as e:
        logger.error(f"❌ Failed to send subscription notification to owner: {str(e)}")


async def send_provider_payment_notification(
    client: Client, contract: Contract, user: User, payment_id: str
):
    """Send paid invoice confirmation email to service provider"""
    try:
        from ..models import BusinessConfig

        db = next(get_db())
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

        # Business name available for future email customization
        client_name = client.contact_name or client.business_name

        if user.email:
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">💰 Payment Received!</h1>
                </div>

                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 20px;">
                        Hi {user.full_name or 'there'},
                    </p>

                    <p style="font-size: 16px; color: #1e293b; margin-bottom: 25px;">
                        Great news! You've received a payment from <strong>{client_name}</strong>.
                    </p>

                    <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #10b981;">
                        <h2 style="color: #10b981; font-size: 20px; margin-top: 0; margin-bottom: 15px;">
                            📋 Invoice Details
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Invoice Number:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right; font-family: monospace;">
                                    INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Client Name:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right; font-weight: 600;">
                                    {client_name}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Client Email:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.email or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Client Phone:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{client.phone or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Service:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.title}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Amount Paid:</td>
                                <td style="padding: 8px 0; color: #10b981; font-weight: bold; font-size: 20px; text-align: right;">
                                    ${contract.total_value:.2f}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Payment Date:</td>
                                <td style="padding: 8px 0; color: #1e293b; text-align: right;">
                                    {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; font-weight: 600;">Payment ID:</td>
                                <td style="padding: 8px 0; color: #64748b; font-size: 11px; text-align: right; font-family: monospace;">
                                    {payment_id}
                                </td>
                            </tr>
                            {f'<tr><td style="padding: 8px 0; color: #64748b; font-weight: 600;">Service Frequency:</td><td style="padding: 8px 0; color: #1e293b; text-align: right;">{contract.frequency.title()}</td></tr>' if contract.frequency else ''}
                        </table>
                    </div>

                    <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                            <strong>💳 Payment Status:</strong> Confirmed<br>
                            <strong>📊 Contract Status:</strong> Active<br>
                            <strong>💰 Payout:</strong> Funds will be deposited according to your Square payout schedule
                        </p>
                    </div>

                    {f'<div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin-bottom: 25px; border-radius: 4px;"><p style="margin: 0; color: #065f46; font-weight: 600;">🔄 Recurring Service Active</p><p style="margin: 8px 0 0 0; color: #1e293b; font-size: 14px;">This client is on a {contract.frequency} subscription. Future payments will be processed automatically.</p></div>' if contract.frequency and contract.frequency.lower() not in ["one-time", "per-turnover", "on-demand", "as-needed"] else ''}

                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{FRONTEND_URL}/dashboard/contracts/{contract.public_id}"
                           style="display: inline-block; background: #10b981; color: white; padding: 14px 28px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                            View Contract Details →
                        </a>
                    </div>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">

                    <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">
                        This payment has been processed through Square. You can view the transaction details
                        in your Square dashboard.
                    </p>

                    <p style="font-size: 14px; color: #1e293b; margin-top: 20px; margin-bottom: 5px;">
                        Best regards,<br>
                        <strong>CleanEnroll</strong>
                    </p>
                </div>

                <div style="text-align: center; padding: 20px; color: #64748b; font-size: 12px;">
                    <p style="margin: 0;">
                        This is an automated payment notification. View details in your dashboard.
                    </p>
                </div>
            </div>
            """

            invoice_number = (
                f"INV-{contract.public_id[:8].upper() if contract.public_id else contract.id}"
            )
            payment_date = datetime.utcnow().strftime("%B %d, %Y")

            mjml_content = payment_received_notification_template(
                provider_name=user.full_name or "there",
                client_name=client_name,
                invoice_number=invoice_number,
                amount=contract.total_value,
                currency="USD",
                payment_date=payment_date,
            )

            await send_email(
                to=user.email,
                subject=f"💰 Payment Received - ${contract.total_value:.2f} from {client_name}",
                mjml_content=mjml_content,
                business_config=business_config,
            )

            logger.info(
                f"✅ Provider payment notification sent to {user.email} for contract {contract.id}"
            )
        else:
            logger.warning(f"⚠️ No email address for provider {user.id}")

    except Exception as e:
        logger.error(f"❌ Failed to send provider payment notification: {str(e)}")


@router.get("/payment-status/{contract_id}")
async def check_payment_status(contract_id: int, db: Session = Depends(get_db)):
    """
    Public endpoint for frontend to check if payment was confirmed
    Used to trigger redirect to payment confirmation page
    """
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        # Check if payment confirmation is pending
        if (
            hasattr(contract, "payment_confirmation_pending")
            and contract.payment_confirmation_pending
        ):
            # Clear the pending flag
            contract.payment_confirmation_pending = False
            db.commit()

            return {
                "payment_confirmed": True,
                "confirmed_at": (
                    contract.payment_confirmed_at.isoformat()
                    if contract.payment_confirmed_at
                    else None
                ),
                "redirect_url": f"/payment-confirmation?contract_id={contract_id}",
                "contract_id": contract_id,
                "amount": float(contract.total_value) if contract.total_value else 0.0,
            }

        return {"payment_confirmed": contract.square_payment_status == "paid", "redirect_url": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking payment status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check payment status")
