"""
Custom SMTP Domain Setup Routes
Allows users to send emails from their own domain via Resend
"""
import logging
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, BusinessConfig
from ..config import RESEND_API_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smtp", tags=["SMTP"])

RESEND_API_URL = "https://api.resend.com"


class SetupSMTPRequest(BaseModel):
    email: EmailStr  # e.g., bookings@preclean.com


class SMTPStatusResponse(BaseModel):
    enabled: bool
    smtp_email: Optional[str]
    smtp_domain: Optional[str]
    status: Optional[str]  # pending, verified, failed
    verified_records: int
    total_records: int
    dns_records: Optional[list]


class DNSRecord(BaseModel):
    type: str  # MX, TXT, CNAME
    name: str
    value: str
    priority: Optional[int] = None
    status: str  # pending, verified


@router.post("/setup")
async def setup_smtp_domain(
    request: SetupSMTPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Setup custom SMTP domain for sending emails.
    Creates domain in Resend and returns DNS records for user to configure.
    """
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    # Extract domain from email
    email = request.email
    domain = email.split("@")[1]
    
    logger.info(f"Setting up SMTP domain {domain} for user {current_user.id}")
    
    # Get or create business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    if not config:
        config = BusinessConfig(user_id=current_user.id)
        db.add(config)
        db.commit()
        db.refresh(config)
    
    # Check if domain already exists in Resend
    try:
        async with httpx.AsyncClient() as client:
            # First, check if we already have this domain
            if config.resend_domain_id and config.smtp_domain == domain:
                # Domain already set up, just return the DNS records
                response = await client.get(
                    f"{RESEND_API_URL}/domains/{config.resend_domain_id}",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}"}
                )
                if response.status_code == 200:
                    domain_data = response.json()
                    dns_records = _format_dns_records(domain_data.get("records", []))
                    
                    # Update config
                    config.smtp_dns_records = dns_records
                    db.commit()
                    
                    return {
                        "success": True,
                        "message": "Domain already configured",
                        "domain": domain,
                        "email": email,
                        "dns_records": dns_records,
                        "resend_domain_id": config.resend_domain_id,
                    }
            
            # Create new domain in Resend
            response = await client.post(
                f"{RESEND_API_URL}/domains",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={"name": domain}
            )
            
            if response.status_code == 409:
                # Domain already exists in Resend (maybe from another user or previous attempt)
                # Try to get the domain info
                list_response = await client.get(
                    f"{RESEND_API_URL}/domains",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}"}
                )
                if list_response.status_code == 200:
                    domains = list_response.json().get("data", [])
                    existing_domain = next((d for d in domains if d.get("name") == domain), None)
                    if existing_domain:
                        domain_id = existing_domain.get("id")
                        dns_records = _format_dns_records(existing_domain.get("records", []))
                        
                        # Update config
                        config.smtp_email = email
                        config.smtp_domain = domain
                        config.resend_domain_id = domain_id
                        config.smtp_status = "pending"
                        config.smtp_dns_records = dns_records
                        config.smtp_verified_records = 0
                        db.commit()
                        
                        return {
                            "success": True,
                            "message": "Domain configured (existing)",
                            "domain": domain,
                            "email": email,
                            "dns_records": dns_records,
                            "resend_domain_id": domain_id,
                        }
                
                raise HTTPException(
                    status_code=400, 
                    detail="This domain is already registered. Please contact support if you own this domain."
                )
            
            if response.status_code not in (200, 201):
                error_detail = response.json().get("message", "Failed to create domain")
                logger.error(f"Resend API error: {response.status_code} - {error_detail}")
                raise HTTPException(status_code=400, detail=error_detail)
            
            domain_data = response.json()
            domain_id = domain_data.get("id")
            dns_records = _format_dns_records(domain_data.get("records", []))
            
            # Update business config
            config.smtp_email = email
            config.smtp_domain = domain
            config.resend_domain_id = domain_id
            config.smtp_status = "pending"
            config.smtp_dns_records = dns_records
            config.smtp_verified_records = 0
            db.commit()
            
            logger.info(f"SMTP domain {domain} created successfully for user {current_user.id}")
            
            return {
                "success": True,
                "message": "Domain created successfully",
                "domain": domain,
                "email": email,
                "dns_records": dns_records,
                "resend_domain_id": domain_id,
            }
            
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Resend API: {e}")
        raise HTTPException(status_code=503, detail="Email service temporarily unavailable")


@router.post("/verify")
async def verify_smtp_domain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check verification status of SMTP domain DNS records.
    Triggers Resend to re-check DNS records.
    """
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    if not config or not config.resend_domain_id:
        raise HTTPException(status_code=404, detail="No SMTP domain configured")
    
    try:
        async with httpx.AsyncClient() as client:
            # Trigger verification
            verify_response = await client.post(
                f"{RESEND_API_URL}/domains/{config.resend_domain_id}/verify",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"}
            )
            
            # Get updated domain status
            response = await client.get(
                f"{RESEND_API_URL}/domains/{config.resend_domain_id}",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to check domain status")
            
            domain_data = response.json()
            records = domain_data.get("records", [])
            dns_records = _format_dns_records(records)
            
            # Count verified records
            verified_count = sum(1 for r in records if r.get("status") == "verified")
            total_records = len(records)
            
            # Determine overall status
            if domain_data.get("status") == "verified" or verified_count == total_records:
                status = "verified"
            elif verified_count > 0:
                status = "pending"
            else:
                status = "pending"
            
            # Update config
            config.smtp_status = status
            config.smtp_dns_records = dns_records
            config.smtp_verified_records = verified_count
            db.commit()
            
            return {
                "success": True,
                "status": status,
                "verified_records": verified_count,
                "total_records": total_records,
                "dns_records": dns_records,
                "domain_status": domain_data.get("status"),
            }
            
    except httpx.RequestError as e:
        logger.error(f"Failed to verify domain: {e}")
        raise HTTPException(status_code=503, detail="Email service temporarily unavailable")


@router.get("/status")
async def get_smtp_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SMTPStatusResponse:
    """Get current SMTP domain configuration status."""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    
    if not config or not config.smtp_domain:
        return SMTPStatusResponse(
            enabled=False,
            smtp_email=None,
            smtp_domain=None,
            status=None,
            verified_records=0,
            total_records=0,
            dns_records=None,
        )
    
    dns_records = config.smtp_dns_records or []
    
    return SMTPStatusResponse(
        enabled=True,
        smtp_email=config.smtp_email,
        smtp_domain=config.smtp_domain,
        status=config.smtp_status,
        verified_records=config.smtp_verified_records or 0,
        total_records=len(dns_records),
        dns_records=dns_records,
    )


@router.delete("/remove")
async def remove_smtp_domain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove custom SMTP domain and revert to default CleanEnroll emails."""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="No configuration found")
    
    # Note: We don't delete from Resend as other users might use the same domain
    # Just clear our local config
    config.smtp_email = None
    config.smtp_domain = None
    config.resend_domain_id = None
    config.smtp_status = None
    config.smtp_dns_records = None
    config.smtp_verified_records = 0
    db.commit()
    
    return {"success": True, "message": "Custom SMTP domain removed"}


def _format_dns_records(records: list) -> list:
    """Format Resend DNS records for frontend display."""
    formatted = []
    for record in records:
        formatted.append({
            "type": record.get("record_type", record.get("type", "TXT")),
            "name": record.get("name", ""),
            "value": record.get("value", ""),
            "priority": record.get("priority"),
            "status": record.get("status", "pending"),
            "ttl": record.get("ttl", "Auto"),
        })
    return formatted
