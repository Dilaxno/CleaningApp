"""
Background jobs for contract signing performance optimization.
Moves PDF regeneration and email sending to async workers.
"""

import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .database import get_db
from .models import Contract, Client, User, BusinessConfig
from .email_service import (
    send_contract_fully_executed_email,
    send_provider_contract_signed_confirmation,
    send_contract_signed_notification
)

logger = logging.getLogger(__name__)

async def regenerate_contract_pdf_job(
    contract_id: int,
    user_id: int,
    signature_type: str = "provider"  # "provider" or "client"
):
    """
    Background job to regenerate contract PDF with signatures.
    This removes the 5-30 second PDF generation from the signing request.
    """
    logger.info(f"🔄 Starting PDF regeneration job for contract {contract_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get contract with relationships
        contract = db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.user_id == user_id
        ).first()
        
        if not contract:
            logger.error(f"❌ Contract {contract_id} not found for PDF regeneration")
            return
        
        # Get client and business config
        client = db.query(Client).filter(Client.id == contract.client_id).first()
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user_id).first()
        
        if not client or not business_config:
            logger.error(f"❌ Missing client or business config for contract {contract_id}")
            return
        
        # Import PDF generation functions
        import hashlib
        from .routes.contracts_pdf import generate_contract_html, html_to_pdf, calculate_quote
        from .routes.upload import get_r2_client, R2_BUCKET_NAME
        
        # Get form data for regeneration
        form_data = client.form_data if client.form_data else {}
        quote = calculate_quote(business_config, form_data)
        
        # Generate HTML with signatures
        html = await generate_contract_html(
            business_config,
            client,
            form_data,
            quote,
            client_signature=contract.client_signature,
            provider_signature=contract.provider_signature,
            contract_created_at=contract.created_at
        )
        
        # Convert to PDF
        pdf_bytes = await html_to_pdf(html)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Upload to R2
        r2 = get_r2_client()
        pdf_key = f"contracts/{user_id}/{contract_id}_{signature_type}_signed.pdf"
        r2.put_object(
            Bucket=R2_BUCKET_NAME, 
            Key=pdf_key, 
            Body=pdf_bytes, 
            ContentType="application/pdf"
        )
        
        # Update contract with new PDF
        contract.pdf_key = pdf_key
        contract.pdf_hash = pdf_hash
        db.commit()
        
        logger.info(f"✅ PDF regeneration completed for contract {contract_id}: {pdf_key}")
        
    except Exception as e:
        logger.error(f"❌ PDF regeneration failed for contract {contract_id}: {e}")
    finally:
        db.close()


async def send_contract_emails_job(
    contract_id: int,
    user_id: int,
    email_type: str = "provider_signed"  # "provider_signed" or "client_signed"
):
    """
    Background job to send contract signing notification emails.
    This removes the 1-5 second email sending from the signing request.
    """
    logger.info(f"📧 Starting email job for contract {contract_id}, type: {email_type}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get contract with relationships
        contract = db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.user_id == user_id
        ).first()
        
        if not contract:
            logger.error(f"❌ Contract {contract_id} not found for email sending")
            return
        
        # Get related data
        client = db.query(Client).filter(Client.id == contract.client_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user_id).first()
        
        if not client or not user:
            logger.error(f"❌ Missing client or user for contract {contract_id}")
            return
        
        # Prepare email data
        from .routes.upload import get_pdf_url
        pdf_url = get_pdf_url(contract.pdf_key) if contract.pdf_key else None
        business_name = business_config.business_name if business_config else "Cleaning Service"
        service_type = contract.contract_type or "Cleaning Service"
        start_date = contract.start_date.strftime("%B %d, %Y") if contract.start_date else None
        property_address = getattr(client, 'address', None)
        business_phone = getattr(business_config, 'business_phone', None) if business_config else None
        
        if email_type == "provider_signed":
            # Send emails when provider signs (contract fully executed)
            
            # Email to client
            if client.email:
                try:
                    await send_contract_fully_executed_email(
                        to=client.email,
                        client_name=client.contact_name or client.business_name,
                        business_name=business_name,
                        contract_title=contract.title,
                        contract_id=contract.id,
                        service_type=service_type,
                        start_date=start_date,
                        total_value=contract.total_value,
                        property_address=property_address,
                        business_phone=business_phone,
                        contract_pdf_url=pdf_url,
                        contract_public_id=contract.public_id
                    )
                    logger.info(f"✅ Sent fully executed contract email to {client.email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send client email: {e}")
            
            # Email to provider
            if user.email:
                try:
                    await send_provider_contract_signed_confirmation(
                        to=user.email,
                        provider_name=user.full_name or "Provider",
                        contract_id=contract.id,
                        client_name=client.business_name,
                        property_address=property_address,
                        contract_pdf_url=pdf_url
                    )
                    logger.info(f"✅ Sent provider confirmation email to {user.email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send provider email: {e}")
        
        elif email_type == "client_signed":
            # Send email when client signs (notify provider)
            if user.email:
                try:
                    await send_contract_signed_notification(
                        to=user.email,
                        provider_name=user.full_name or "Provider",
                        client_name=client.business_name,
                        contract_title=contract.title,
                        contract_id=contract.id,
                        contract_pdf_url=pdf_url
                    )
                    logger.info(f"✅ Sent client signed notification to {user.email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send provider notification: {e}")
        
        logger.info(f"✅ Email job completed for contract {contract_id}")
        
    except Exception as e:
        logger.error(f"❌ Email job failed for contract {contract_id}: {e}")
    finally:
        db.close()


async def upload_client_signature_job(
    contract_id: int,
    user_id: int,
    signature_data: str
):
    """
    Background job to upload client signature to R2 storage.
    This removes the 1-3 second upload from the signing request.
    """
    logger.info(f"📤 Starting signature upload job for contract {contract_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get contract
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"❌ Contract {contract_id} not found for signature upload")
            return
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"❌ User {user_id} not found for signature upload")
            return
        
        # Upload client signature to R2 for PDF rendering
        if signature_data and signature_data.startswith("data:image"):
            try:
                import base64
                import uuid
                from .routes.upload import get_r2_client, R2_BUCKET_NAME, generate_presigned_url
                
                # Extract base64 data from data URL
                header, encoded = signature_data.split(",", 1)
                signature_bytes = base64.b64decode(encoded)
                
                # Upload to R2
                signature_key = f"signatures/clients/{user.firebase_uid}/{uuid.uuid4()}.png"
                r2_client = get_r2_client()
                r2_client.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=signature_key,
                    Body=signature_bytes,
                    ContentType="image/png"
                )
                
                logger.info(f"✅ Client signature uploaded to R2: {signature_key}")
                
            except Exception as sig_err:
                logger.error(f"❌ Failed to upload client signature to R2: {sig_err}")
        
    except Exception as e:
        logger.error(f"❌ Signature upload job failed for contract {contract_id}: {e}")
    finally:
        db.close()


async def increment_client_count_job(user_id: int):
    """
    Background job to increment client count for plan limits.
    This removes database writes from the signing request.
    """
    try:
        db = next(get_db())
        
        from .plan_limits import increment_client_count
        user = db.query(User).filter(User.id == user_id).first()
        
        if user:
            increment_client_count(user, db)
            logger.info(f"📊 Client count incremented for user {user_id}: {user.clients_this_month}")
        
    except Exception as e:
        logger.error(f"❌ Failed to increment client count for user {user_id}: {e}")
    finally:
        db.close()