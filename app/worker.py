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
            quote_amount=quote.get("total", 0),
            status="pending_signature" if not signature else "signed",
            metadata={
                "quote": quote,
                "form_data": form_data,
                "generated_at": datetime.now().isoformat()
            }
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


class WorkerSettings:
    """ARQ Worker Settings"""
    functions = [generate_contract_pdf_task]
    redis_settings = get_redis_settings()
    max_jobs = 5  # Concurrency limit: max 5 PDF generations at once
    job_timeout = 300  # 5 minutes timeout per job
    keep_result = 3600  # Keep job results for 1 hour
