"""
ARQ Background Worker for Async Jobs
Handles contract generation and other long-running tasks
"""
import logging
import os
import asyncio
from arq import create_pool
from arq.connections import RedisSettings

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
            host=parsed.hostname or 'localhost',
            port=parsed.port or 6379,
            password=parsed.password,
            ssl=parsed.scheme == 'rediss'
        )
    else:
        # Use individual settings
        return RedisSettings(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true"
        )


async def generate_contract_pdf_task(ctx, client_id: int, owner_uid: str, form_data: dict, signature: str = None):
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
    from .database import SessionLocal
    from .models import User, Client, Contract, BusinessConfig
    from .routes.contracts_pdf import calculate_quote, generate_contract_html, html_to_pdf
    from .routes.upload import get_r2_client, generate_presigned_url
    from .config import R2_BUCKET_NAME
    from datetime import datetime
    
    logger.info(f"📄 Starting contract PDF generation for client {client_id}")
    
    db = SessionLocal()
    try:
        # Get user and client
        user = db.query(User).filter(User.firebase_uid == owner_uid).first()
        if not user:
            raise Exception(f"User not found: {owner_uid}")
        
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise Exception(f"Client not found: {client_id}")
        
        # Get business config
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if not config:
            raise Exception("Business config not found")
        
        # Calculate quote
        quote = calculate_quote(config, form_data)
        logger.info(f"💰 Quote calculated: {quote}")
        
        # Generate HTML
        html = await generate_contract_html(config, client, form_data, quote, signature)
        logger.info(f"📝 HTML generated: {len(html)} chars")
        
        # Generate PDF
        pdf_bytes = await html_to_pdf(html)
        logger.info(f"✅ PDF generated: {len(pdf_bytes)} bytes")
        
        # Upload to R2
        pdf_key = f"contracts/{user.firebase_uid}/{client.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        
        r2_client = get_r2_client()
        r2_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=pdf_key,
            Body=pdf_bytes,
            ContentType="application/pdf"
        )
        
        # Generate presigned URL (7 days)
        pdf_url = generate_presigned_url(pdf_key, expiration=604800)
        
        # Create contract record
        contract = Contract(
            user_id=user.id,
            client_id=client.id,
            title=f"Cleaning Contract - {client.business_name or client.contact_name}",
            pdf_key=pdf_key,
            total_value=quote.get("final_price", quote.get("total", 0)),
            status="new" if not signature else "signed",
        )
        
        if signature:
            contract.client_signature = signature
            contract.signed_at = datetime.now()
        
        db.add(contract)
        db.commit()
        db.refresh(contract)
        
        logger.info(f"✅ Contract created: ID={contract.id}, PDF uploaded to R2")
        
        return {
            "contract_id": contract.id,
            "pdf_url": pdf_url,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Contract generation failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


async def send_form_notification_emails_task(ctx, client_id: int, user_id: int, owner_uid: str):
    """
    Background task to send email notifications for form submissions
    
    Args:
        ctx: ARQ context
        client_id: Client ID
        user_id: User ID
        owner_uid: Business owner Firebase UID
    """
    from .database import SessionLocal
    from .models import User, Client, BusinessConfig
    from .email_service import send_new_client_notification, send_form_submission_confirmation
    
    logger.info(f"📧 Starting email notifications for client {client_id}")
    
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
        if user.email:
            await send_new_client_notification(
                to=user.email,
                business_name=business_name,
                client_name=client.contact_name or client.business_name,
                client_email=client.email or "Not provided",
                property_type=client.property_type or "Not specified",
            )
            logger.info(f"✅ Notification email sent to business owner: {user.email}")
        
        # Send confirmation to client
        if client.email:
            await send_form_submission_confirmation(
                to=client.email,
                client_name=client.contact_name or client.business_name,
                business_name=business_name,
                property_type=client.property_type or "Property",
            )
            logger.info(f"✅ Confirmation email sent to client: {client.email}")
        
        return {"status": "completed", "emails_sent": 2 if user.email and client.email else 1 if user.email or client.email else 0}
        
    except Exception as e:
        logger.error(f"❌ Email notification failed: {str(e)}")
        raise
    finally:
        db.close()


class WorkerSettings:
    """ARQ Worker Settings"""
    functions = [generate_contract_pdf_task, send_form_notification_emails_task]
    redis_settings = get_redis_settings()
    max_jobs = 10  # Concurrency limit: max 10 jobs at once (5 PDF + 5 emails)
    job_timeout = 300  # 5 minutes timeout per job
    keep_result = 3600  # Keep job results for 1 hour
