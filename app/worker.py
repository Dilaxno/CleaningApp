"""
ARQ Background Worker for Async Jobs
Handles contract generation and other long-running tasks
"""

import logging
import os

from arq.connections import RedisSettings

# Import all models at module level to ensure SQLAlchemy can resolve relationships
# This must happen before any database operations
from .database import SessionLocal

# Import all model files to ensure all models are registered
from . import models  # noqa: F401 - Main models
from . import models_invoice  # noqa: F401 - Invoice models
from . import models_google_calendar  # noqa: F401 - Google Calendar models
from . import models_quickbooks  # noqa: F401 - QuickBooks models
from . import models_square  # noqa: F401 - Square models
from . import models_twilio  # noqa: F401 - Twilio models
from . import models_visit  # noqa: F401 - Visit models

# Import specific models needed for type hints
from .models import BusinessConfig, Client, Contract, User

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Get Redis settings for ARQ worker"""
    redis_url = os.getenv("REDIS_URL")

    if redis_url:
        # Parse Redis URL for ARQ
        # Format: rediss://default:password@host:port
        from urllib.parse import urlparse

        parsed = urlparse(redis_url)

        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password,
            ssl=parsed.scheme == "rediss",
            conn_timeout=15,  # Connection timeout
            conn_retry_delay=1,  # Retry delay in seconds
        )
    else:
        # Use individual settings
        return RedisSettings(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
            conn_timeout=15,  # Connection timeout
            conn_retry_delay=1,  # Retry delay in seconds
        )


async def generate_contract_pdf_task(
    ctx, client_id: int, owner_uid: str, form_data: dict, signature: str = None
):
    """
    Background task to generate contract PDF

    Args:
        ctx: ARQ context
        client_id: Client ID
        owner_uid: Business owner Firebase UID
        form_data: Form data for quote calculation
        signature: Optional client signature (base64)

    Returns:
        dict with contract_id and pdf_url
    """
    from datetime import datetime

    from .config import R2_BUCKET_NAME
    from .routes.contracts_pdf import calculate_quote, generate_contract_html, html_to_pdf
    from .routes.upload import get_r2_client

    logger.info(f"🚀 ARQ Worker: Starting contract PDF generation for client {client_id}")
    logger.info(f"📋 Job ID: {ctx.get('job_id', 'unknown')}")

    db = SessionLocal()
    try:
        # Get user and client
        logger.info(f"🔍 Fetching user with Firebase UID: {owner_uid}")
        user = db.query(User).filter(User.firebase_uid == owner_uid).first()
        if not user:
            logger.error(f"❌ User not found: {owner_uid}")
            raise Exception(f"User not found: {owner_uid}")
        logger.info(f"✅ User found: ID={user.id}, Email={user.email}")

        logger.info(f"🔍 Fetching client: {client_id}")
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(f"❌ Client not found: {client_id}")
            raise Exception(f"Client not found: {client_id}")
        logger.info(f"✅ Client found: {client.business_name or client.contact_name}")

        # Get business config
        logger.info(f"🔍 Fetching business config for user {user.id}")
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if not config:
            logger.error(f"❌ Business config not found for user {user.id}")
            raise Exception("Business config not found")
        logger.info(f"✅ Business config found: {config.business_name}")

        # Calculate quote
        try:
            logger.info(f"💰 Calculating quote...")
            quote = calculate_quote(config, form_data)
            logger.info(f"✅ Quote calculated: ${quote.get('total', 0)}")
        except Exception as e:
            logger.error(f"❌ Quote calculation failed: {str(e)}")
            raise Exception(f"Failed to calculate quote: {str(e)}") from e

        # Create contract record first to get public_id for secure contract numbering
        logger.info(f"📝 Creating contract record...")
        contract = Contract(
            user_id=user.id,
            client_id=client_id,
            title=f"Cleaning Contract - {client.business_name or client.contact_name}",
            total_value=quote.get("final_price", quote.get("total", 0)),
            status="new" if not signature else "signed",
        )

        if signature:
            contract.client_signature = signature
            contract.signed_at = datetime.now()

        db.add(contract)
        db.commit()
        db.refresh(contract)

        logger.info(f"✅ Contract created: ID={contract.id}, Public ID={contract.public_id}")

        # Generate HTML with contract public_id for secure contract numbering
        try:
            logger.info(f"📄 Generating contract HTML...")
            html = await generate_contract_html(
                config,
                client,
                form_data,
                quote,
                db,
                client_signature=signature,
                contract_public_id=contract.public_id,
            )
            logger.info(f"✅ Contract HTML generated ({len(html)} chars)")
        except Exception as e:
            logger.error(f"❌ HTML generation failed: {str(e)}")
            db.rollback()
            raise Exception(f"Failed to generate contract HTML: {str(e)}") from e

        # Generate PDF
        try:
            logger.info(f"📄 Converting HTML to PDF...")
            pdf_bytes = await html_to_pdf(html)
            logger.info(f"✅ PDF generated ({len(pdf_bytes)} bytes)")
        except Exception as e:
            logger.error(f"❌ PDF generation failed: {str(e)}")
            db.rollback()
            raise Exception(f"Failed to generate PDF: {str(e)}") from e

        # Upload to R2
        pdf_key = f"contracts/{user.firebase_uid}/{contract.public_id}.pdf"

        try:
            logger.info(f"📤 Uploading PDF to R2: {pdf_key}")
            r2_client = get_r2_client()
            r2_client.put_object(
                Bucket=R2_BUCKET_NAME, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf"
            )
            logger.info(f"✅ PDF uploaded to R2: {pdf_key}")
        except Exception as e:
            logger.error(f"❌ R2 upload failed: {str(e)}")
            db.rollback()
            raise Exception(f"Failed to upload PDF to storage: {str(e)}") from e

        # Update contract with PDF key
        contract.pdf_key = pdf_key
        db.commit()

        # Generate presigned URL (7 days)
        # Generate backend URL instead of presigned R2 URL to avoid CORS issues
        from .config import FRONTEND_URL

        # Determine the backend base URL based on the frontend URL
        if "localhost" in FRONTEND_URL:
            backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace(
                "localhost:5174", "localhost:8000"
            )
        else:
            backend_base = "https://api.cleanenroll.com"

        # Generate backend PDF URL using public_id
        backend_pdf_url = f"{backend_base}/contracts/pdf/public/{contract.public_id}"

        logger.info(
            f"✅ ARQ Worker: Contract generation completed successfully: ID={contract.id}, Public ID={contract.public_id}"
        )

        return {"contract_id": contract.id, "pdf_url": backend_pdf_url, "status": "completed"}

    except Exception as e:
        logger.error(f"❌ ARQ Worker: Contract generation failed: {type(e).__name__}: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.info(f"🔒 Database connection closed for client {client_id}")


async def send_form_notification_emails_task(_ctx, client_id: int, user_id: int, owner_uid: str):
    """
    Background task to send email notifications for form submissions

    Args:
        ctx: ARQ context
        client_id: Client ID
        user_id: User ID
        owner_uid: Business owner Firebase UID
    """
    from .email_service import send_form_submission_confirmation, send_new_client_notification

    logger.info(f"Starting email notifications for client {client_id}")

    db = SessionLocal()
    try:
        # Get user and client
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(f"User not found: {user_id}")

        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise Exception(f"Client not found: {client_id}")

        # Get business config
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        business_name = config.business_name if config else "Your Business"

        # Send notification to business owner
        emails_sent = 0
        if user.email:
            try:
                # Extract property shots from form data
                form_data = client.form_data or {}
                property_shots_keys = form_data.get("propertyShots", [])
                if isinstance(property_shots_keys, str):
                    property_shots_keys = [property_shots_keys]

                await send_new_client_notification(
                    to=user.email,
                    business_name=business_name,
                    client_name=client.contact_name or client.business_name,
                    client_email=client.email or "Not provided",
                    property_type=client.property_type or "Not specified",
                    property_shots_keys=property_shots_keys,
                )
                logger.info(f"✅ New client notification sent to business owner: {user.email}")
                emails_sent += 1
            except Exception as e:
                logger.error(
                    f"❌ Failed to send notification to business owner {user.email}: {str(e)}"
                )
                # Don't raise - continue with client email

        # Send confirmation to client
        if client.email:
            try:
                await send_form_submission_confirmation(
                    to=client.email,
                    client_name=client.contact_name or client.business_name,
                    business_name=business_name,
                    property_type=client.property_type or "Property",
                )
                logger.info(f"✅ Form confirmation sent to client: {client.email}")
                emails_sent += 1
            except Exception as e:
                logger.error(f"❌ Failed to send confirmation to client {client.email}: {str(e)}")
                # Don't raise - at least one email might have succeeded

        return {"status": "completed", "emails_sent": emails_sent}

    except Exception as e:
        logger.error(f"❌ Email notification failed: {str(e)}")
        raise
    finally:
        db.close()


async def smtp_health_check_task(ctx):
    """
    Daily cron job to verify all custom SMTP connections.
    Updates status to 'failed' if connection fails, allowing fallback to CleanEnroll.
    """
    from datetime import datetime

    from .routes.smtp import decrypt_password, test_smtp_connection

    logger.info("Starting daily SMTP health check")

    db = SessionLocal()
    try:
        # Get all configs with custom SMTP configured
        configs = (
            db.query(BusinessConfig)
            .filter(BusinessConfig.smtp_host.isnot(None), BusinessConfig.smtp_email.isnot(None))
            .all()
        )

        logger.info(f"Checking {len(configs)} SMTP configurations")

        checked = 0
        failed = 0

        for config in configs:
            try:
                success, message = test_smtp_connection(
                    host=config.smtp_host,
                    port=config.smtp_port or 587,
                    username=config.smtp_username,
                    password=decrypt_password(config.smtp_password),
                    from_email=config.smtp_email,
                    use_tls=config.smtp_use_tls if config.smtp_use_tls is not None else True,
                )

                config.smtp_last_test_at = datetime.utcnow()
                config.smtp_last_test_success = success

                if success:
                    config.smtp_status = "live"
                    config.smtp_error_message = None
                else:
                    config.smtp_status = "failed"
                    config.smtp_error_message = message
                    failed += 1
                    logger.warning(f"⚠️ SMTP check failed for user {config.user_id}: {message}")

                checked += 1

            except Exception as e:
                config.smtp_status = "failed"
                config.smtp_error_message = str(e)
                config.smtp_last_test_at = datetime.utcnow()
                config.smtp_last_test_success = False
                failed += 1
                logger.error(f"❌ SMTP check error for user {config.user_id}: {e}")

        db.commit()
        logger.info(f"SMTP health check complete: {checked} checked, {failed} failed")

        return {"checked": checked, "failed": failed}

    except Exception as e:
        logger.error(f"❌ SMTP health check failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


async def status_automation_task(ctx):
    """
    Daily cron job to update contract and client statuses based on dates.
    - Contracts: signed → active (when start date arrives)
    - Contracts: active → completed (when end date passes)
    - Clients: scheduled → active (when first accepted schedule date arrives)
    """
    from .services.status_automation import update_contract_statuses

    logger.info("Starting daily status automation")

    db = SessionLocal()
    try:
        summary = update_contract_statuses(db)
        logger.info(f"Status automation complete: {summary}")
        return summary
    except Exception as e:
        logger.error(f"❌ Status automation failed: {str(e)}")
        raise
    finally:
        db.close()


async def reset_monthly_client_limits_task(ctx):
    """
    Daily cron job to proactively reset monthly client limits for users
    whose billing cycle has completed (every 30 days from subscription start).
    This ensures limits are refreshed even when users are inactive.
    """
    from .plan_limits import check_and_reset_monthly_counter

    logger.info("🔄 Starting monthly client limit reset check")

    db = SessionLocal()
    try:
        # Get all users with active subscriptions
        users = db.query(User).filter(User.plan.isnot(None)).all()

        reset_count = 0
        checked_count = 0

        for user in users:
            try:
                # Record current count before check
                before_count = user.clients_this_month

                # Check and reset if needed
                check_and_reset_monthly_counter(user, db)

                # If counter was reset, increment our counter
                if user.clients_this_month < before_count or (
                    before_count > 0 and user.clients_this_month == 0
                ):
                    reset_count += 1

                checked_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to check/reset limits for user {user.id}: {str(e)}")
                continue

        logger.info(
            f"Monthly limit reset complete: checked {checked_count} users, reset {reset_count} users"
        )

        return {"checked": checked_count, "reset": reset_count}

    except Exception as e:
        logger.error(f"❌ Monthly limit reset failed: {str(e)}")
        raise
    finally:
        db.close()


class WorkerSettings:
    """ARQ Worker Settings - Optimized for Scale"""

    functions = [
        generate_contract_pdf_task,
        send_form_notification_emails_task,
        smtp_health_check_task,
        status_automation_task,
        reset_monthly_client_limits_task,
    ]
    redis_settings = get_redis_settings()

    # Scalability settings - adjust based on server resources
    # For 2GB RAM: max_jobs=10, For 4GB RAM: max_jobs=20, For 8GB RAM: max_jobs=40
    max_jobs = int(os.getenv("ARQ_MAX_JOBS", "20"))  # Increased from 10 to 20
    job_timeout = int(os.getenv("ARQ_JOB_TIMEOUT", "600"))  # Increased to 10 minutes
    keep_result = int(os.getenv("ARQ_KEEP_RESULT", "3600"))  # Keep job results for 1 hour

    # Health check settings
    health_check_interval = 60  # Check worker health every 60 seconds

    # Retry settings for failed jobs
    max_tries = 3  # Retry failed jobs up to 3 times

    # Cron jobs - run daily
    from arq.cron import cron

    cron_jobs = [
        cron(smtp_health_check_task, hour=6, minute=0),  # 6 AM UTC
        cron(
            status_automation_task, hour=0, minute=5
        ),  # 12:05 AM UTC - update statuses at start of day
        cron(
            reset_monthly_client_limits_task, hour=0, minute=10
        ),  # 12:10 AM UTC - reset monthly client limits
    ]

    logger.info(f"🔧 ARQ Worker configured: max_jobs={max_jobs}, timeout={job_timeout}s")
