"""
Trial Contract Generation Routes
Allows users to test contract generation without signup
Limited to 1 contract per session ID + IP address
"""
import logging
import hashlib
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trial", tags=["Trial"])


class TrialFormData(BaseModel):
    clientName: str
    clientEmail: Optional[EmailStr] = None
    businessName: str
    propertyType: str
    squareFootage: int
    cleaningFrequency: str
    numberOfRooms: Optional[int] = None
    address: Optional[str] = None


class TrialCheckRequest(BaseModel):
    sessionId: str


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    # Check for forwarded IP first (for proxies/load balancers)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct connection IP
    if request.client:
        return request.client.host
    
    return "unknown"


def hash_identifier(session_id: str, ip_address: str) -> str:
    """Create a hash of session + IP for privacy"""
    combined = f"{session_id}:{ip_address}"
    return hashlib.sha256(combined.encode()).hexdigest()


@router.post("/check-eligibility")
async def check_trial_eligibility(
    data: TrialCheckRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Check if user is eligible for free trial
    Returns: { eligible: bool, reason?: string }
    """
    try:
        ip_address = get_client_ip(request)
        
        # Check if this session + IP combo already used trial
        query = text("""
            SELECT id FROM trial_contracts 
            WHERE session_id = :session_id AND ip_address = :ip_address
            LIMIT 1
        """)
        
        result = db.execute(query, {"session_id": data.sessionId, "ip_address": ip_address}).fetchone()
        
        if result:
            return {
                "eligible": False,
                "reason": "You've already used your free trial. Sign up to create unlimited contracts!"
            }
        
        return {"eligible": True}
        
    except Exception as e:
        logger.error(f"Error checking trial eligibility: {e}")
        raise HTTPException(status_code=500, detail="Failed to check eligibility")


@router.post("/generate-contract")
async def generate_trial_contract(
    data: TrialFormData,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Generate a free trial contract
    Limited to 1 per session + IP combination
    """
    try:
        # Get session ID from header
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID required")
        
        ip_address = get_client_ip(request)
        
        # Check if already used trial
        check_query = text("""
            SELECT id FROM trial_contracts 
            WHERE session_id = :session_id AND ip_address = :ip_address
            LIMIT 1
        """)
        
        existing = db.execute(check_query, {
            "session_id": session_id,
            "ip_address": ip_address
        }).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=403,
                detail="Trial limit reached. Sign up to create unlimited contracts!"
            )
        
        # Generate trial contract using default business config
        from .contracts_pdf import calculate_quote, generate_contract_html, html_to_pdf, upload_pdf_to_r2
        
        # Create mock business config for trial
        trial_config = type('obj', (object,), {
            'business_name': 'CleanEnroll Demo',
            'logo_url': None,
            'signature_url': None,
            'pricing_model': 'sqft',
            'rate_per_sqft': 0.15,
            'rate_per_room': None,
            'hourly_rate': None,
            'flat_rate': None,
            'minimum_charge': 75,
            'payment_due_days': 15,
            'late_fee_percent': 1.5,
            'cleaning_time_per_sqft': 90,
            'cleaners_small_job': 1,
            'cleaners_large_job': 2,
            'discount_weekly': 10.0,
            'discount_monthly': 5.0,
            'discount_long_term': 15.0,
            'standard_inclusions': [
                'Dusting and wiping all surfaces',
                'Vacuuming and mopping floors',
                'Cleaning and sanitizing bathrooms',
                'Kitchen cleaning and countertop sanitization',
                'Trash removal'
            ],
            'standard_exclusions': [
                'Window washing (exterior)',
                'Deep carpet cleaning',
                'Heavy-duty cleaning',
                'Move-in/move-out cleaning'
            ]
        })()
        
        # Create mock client
        trial_client = type('obj', (object,), {
            'id': 0,
            'contact_name': data.clientName,
            'business_name': data.businessName,
            'email': data.clientEmail,
            'phone': None,
            'property_type': data.propertyType
        })()
        
        # Prepare form data
        form_data = {
            'squareFootage': data.squareFootage,
            'cleaningFrequency': data.cleaningFrequency,
            'numberOfRooms': data.numberOfRooms or 0,
            'address': data.address or '',
            'billingAddress': data.address or ''
        }
        
        # Calculate quote
        quote = calculate_quote(trial_config, form_data)
        
        # Generate HTML
        html = await generate_contract_html(
            trial_config,
            trial_client,
            form_data,
            quote,
            None  # No client signature for trial
        )
        
        # Generate PDF
        pdf_bytes = await html_to_pdf(html)
        
        # Upload to R2 with trial prefix
        trial_id = str(uuid.uuid4())
        pdf_key = f"trial-contracts/{trial_id}.pdf"
        
        # Upload to R2
        from .upload import get_r2_client
        from ..config import R2_BUCKET_NAME
        
        r2 = get_r2_client()
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=pdf_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        
        # Store trial usage in database
        insert_query = text("""
            INSERT INTO trial_contracts (
                session_id, ip_address, client_name, client_email,
                business_name, property_type, square_footage,
                cleaning_frequency, contract_data, pdf_key
            ) VALUES (
                :session_id, :ip_address, :client_name, :client_email,
                :business_name, :property_type, :square_footage,
                :cleaning_frequency, :contract_data, :pdf_key
            )
            RETURNING id
        """)
        
        import json
        result = db.execute(insert_query, {
            "session_id": session_id,
            "ip_address": ip_address,
            "client_name": data.clientName,
            "client_email": data.clientEmail,
            "business_name": data.businessName,
            "property_type": data.propertyType,
            "square_footage": data.squareFootage,
            "cleaning_frequency": data.cleaningFrequency,
            "contract_data": json.dumps(form_data),
            "pdf_key": pdf_key
        })
        
        db.commit()
        trial_record_id = result.fetchone()[0]
        
        logger.info(f"✅ Trial contract generated: ID={trial_record_id}, Session={session_id}, IP={ip_address}")
        
        # Generate presigned URL for viewing
        from .upload import generate_presigned_url
        pdf_url = generate_presigned_url(pdf_key, expiration=3600)  # 1 hour expiry
        
        return {
            "success": True,
            "trialId": trial_id,
            "pdfUrl": pdf_url,
            "quote": {
                "basePrice": quote['base_price'],
                "finalPrice": quote['final_price'],
                "frequency": quote['frequency'],
                "estimatedHours": quote['estimated_hours']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating trial contract: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to generate trial contract")


@router.get("/contract/{trial_id}/pdf")
async def get_trial_contract_pdf(
    trial_id: str,
    db: Session = Depends(get_db)
):
    """Get presigned URL for trial contract PDF"""
    try:
        query = text("""
            SELECT pdf_key FROM trial_contracts 
            WHERE pdf_key LIKE :pattern
            LIMIT 1
        """)
        
        result = db.execute(query, {"pattern": f"trial-contracts/{trial_id}.pdf"}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Trial contract not found")
        
        pdf_key = result[0]
        
        # Generate presigned URL
        from .upload import generate_presigned_url
        pdf_url = generate_presigned_url(pdf_key, expiration=3600)
        
        return {"url": pdf_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving trial contract: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve contract")
