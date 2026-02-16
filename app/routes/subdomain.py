"""
Subdomain Verification Routes
Allows users to connect their own subdomains for automated email sending
"""

import logging
import re
import secrets
from datetime import datetime
from typing import Optional

import dns.resolver
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import BusinessConfig, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subdomain", tags=["Subdomain"])


class SubdomainSetupRequest(BaseModel):
    subdomain: str  # e.g., mail.preclean.com

    @validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v):
        if not v:
            raise ValueError("Subdomain is required")

        # Basic domain validation
        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        if not re.match(domain_pattern, v):
            raise ValueError("Invalid subdomain format")

        # Must be a subdomain (contain at least one dot)
        if "." not in v:
            raise ValueError("Must be a subdomain (e.g., mail.yourdomain.com)")

        return v.lower().strip()


class SubdomainStatusResponse(BaseModel):
    configured: bool
    subdomain: Optional[str]
    verification_status: Optional[str]  # pending, verified, failed
    dns_records: Optional[list[dict]]
    verified_at: Optional[str]
    last_check_at: Optional[str]
    verification_token: Optional[str]
    next_steps: Optional[list[str]]


class DNSRecord(BaseModel):
    type: str  # CNAME, TXT, MX
    name: str
    value: str
    priority: Optional[int] = None
    status: str  # pending, verified, failed
    description: str


def generate_verification_token() -> str:
    """Generate a unique verification token for TXT record"""
    return f"cleanenroll-verify-{secrets.token_urlsafe(32)}"


def generate_dns_records(subdomain: str, verification_token: str) -> list[dict]:
    """
    Generate required DNS records for subdomain verification.
    Returns list of DNS records that user needs to configure.
    """
    records = [
        {
            "type": "CNAME",
            "name": subdomain,
            "value": "mail.cleanenroll.com",
            "status": "pending",
            "description": "Points your subdomain to CleanEnroll's email servers",
        },
        {
            "type": "TXT",
            "name": f"_cleanenroll-verification.{subdomain}",
            "value": verification_token,
            "status": "pending",
            "description": "Verification token to prove domain ownership",
        },
        {
            "type": "MX",
            "name": subdomain,
            "value": "mail.cleanenroll.com",
            "priority": 10,
            "status": "pending",
            "description": "Mail exchange record for email delivery",
        },
    ]
    return records


def check_dns_record(
    record_type: str, name: str, expected_value: str, priority: Optional[int] = None
) -> bool:
    """
    Check if a DNS record exists and matches expected value.
    Returns True if record is correctly configured.
    """
    try:
        if record_type == "CNAME":
            answers = dns.resolver.resolve(name, "CNAME")
            for answer in answers:
                if str(answer.target).rstrip(".").lower() == expected_value.lower():
                    return True

        elif record_type == "TXT":
            answers = dns.resolver.resolve(name, "TXT")
            for answer in answers:
                txt_value = "".join(
                    [
                        part.decode() if isinstance(part, bytes) else str(part)
                        for part in answer.strings
                    ]
                )
                if txt_value == expected_value:
                    return True

        elif record_type == "MX":
            answers = dns.resolver.resolve(name, "MX")
            for answer in answers:
                if str(answer.exchange).rstrip(".").lower() == expected_value.lower() and (
                    priority is None or answer.preference == priority
                ):
                    return True

        return False

    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout, Exception) as e:
        logger.debug(f"DNS lookup failed for {record_type} {name}: {e}")
        return False


def verify_subdomain_dns(subdomain: str, dns_records: list[dict]) -> tuple[bool, list[dict]]:
    """
    Verify all DNS records for a subdomain.
    Returns (all_verified, updated_records_with_status)
    """
    updated_records = []
    all_verified = True

    for record in dns_records:
        is_verified = check_dns_record(
            record["type"], record["name"], record["value"], record.get("priority")
        )

        updated_record = record.copy()
        updated_record["status"] = "verified" if is_verified else "pending"
        updated_records.append(updated_record)

        if not is_verified:
            all_verified = False

    return all_verified, updated_records


@router.post("/setup")
async def setup_subdomain(
    request: SubdomainSetupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Setup subdomain for automated emails.
    Generates DNS records that user needs to configure.
    """
    logger.info(f"Setting up subdomain for user {current_user.id}: {request.subdomain}")

    # Get or create business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    if not config:
        config = BusinessConfig(user_id=current_user.id)
        db.add(config)

    # Generate verification token and DNS records
    verification_token = generate_verification_token()
    dns_records = generate_dns_records(request.subdomain, verification_token)

    # Save subdomain configuration
    config.email_subdomain = request.subdomain
    config.subdomain_verification_status = "pending"
    config.subdomain_dns_records = dns_records
    config.subdomain_verification_token = verification_token
    config.subdomain_last_check_at = datetime.utcnow()
    config.subdomain_verified_at = None

    db.commit()

    logger.info(f"Subdomain setup initiated for user {current_user.id}")

    return {
        "success": True,
        "message": "Subdomain setup initiated. Please configure the DNS records.",
        "subdomain": request.subdomain,
        "dns_records": dns_records,
        "verification_token": verification_token,
        "next_steps": [
            "Add the DNS records to your domain provider",
            "Wait for DNS propagation (up to 24 hours)",
            "Click 'Verify DNS Records' to complete setup",
        ],
    }


@router.post("/verify")
async def verify_subdomain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify DNS records for configured subdomain.
    Checks if all required DNS records are properly configured.
    """
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config or not config.email_subdomain:
        raise HTTPException(status_code=400, detail="No subdomain configured")

    if not config.subdomain_dns_records:
        raise HTTPException(status_code=400, detail="No DNS records found")

    logger.info(f"Verifying subdomain DNS for user {current_user.id}: {config.email_subdomain}")

    # Verify DNS records
    all_verified, updated_records = verify_subdomain_dns(
        config.email_subdomain, config.subdomain_dns_records
    )

    # Update configuration
    config.subdomain_dns_records = updated_records
    config.subdomain_last_check_at = datetime.utcnow()

    if all_verified:
        config.subdomain_verification_status = "verified"
        config.subdomain_verified_at = datetime.utcnow()
        message = (
            "Subdomain verified successfully! You can now send emails from your custom domain."
        )
        logger.info(f"Subdomain verified for user {current_user.id}: {config.email_subdomain}")
    else:
        config.subdomain_verification_status = "failed"
        message = "Some DNS records are not configured correctly. Please check your DNS settings."
        logger.warning(
            f"Subdomain verification failed for user {current_user.id}: {config.email_subdomain}"
        )

    db.commit()

    return {
        "success": all_verified,
        "message": message,
        "verification_status": config.subdomain_verification_status,
        "dns_records": updated_records,
        "verified_count": sum(1 for r in updated_records if r["status"] == "verified"),
        "total_records": len(updated_records),
    }


@router.get("/status")
async def get_subdomain_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubdomainStatusResponse:
    """Get current subdomain configuration status."""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config or not config.email_subdomain:
        return SubdomainStatusResponse(
            configured=False,
            subdomain=None,
            verification_status=None,
            dns_records=None,
            verified_at=None,
            last_check_at=None,
            verification_token=None,
            next_steps=["Configure a subdomain to send emails from your own domain"],
        )

    next_steps = []
    if config.subdomain_verification_status == "pending":
        verified_count = sum(
            1 for r in (config.subdomain_dns_records or []) if r.get("status") == "verified"
        )
        total_count = len(config.subdomain_dns_records or [])

        if verified_count == 0:
            next_steps = [
                "Add the DNS records to your domain provider",
                "Wait for DNS propagation (up to 24 hours)",
                "Click 'Verify DNS Records' to check status",
            ]
        elif verified_count < total_count:
            next_steps = [
                f"Configure remaining DNS records ({total_count - verified_count} pending)",
                "Wait for DNS propagation",
                "Click 'Verify DNS Records' to check status",
            ]
        else:
            next_steps = ["Click 'Verify DNS Records' to complete verification"]

    elif config.subdomain_verification_status == "failed":
        next_steps = [
            "Check DNS record configuration with your domain provider",
            "Ensure all records are added correctly",
            "Wait for DNS propagation and try verification again",
        ]

    elif config.subdomain_verification_status == "verified":
        next_steps = ["Your subdomain is ready! Emails will be sent from your custom domain."]

    return SubdomainStatusResponse(
        configured=True,
        subdomain=config.email_subdomain,
        verification_status=config.subdomain_verification_status,
        dns_records=config.subdomain_dns_records,
        verified_at=(
            config.subdomain_verified_at.isoformat() if config.subdomain_verified_at else None
        ),
        last_check_at=(
            config.subdomain_last_check_at.isoformat() if config.subdomain_last_check_at else None
        ),
        verification_token=config.subdomain_verification_token,
        next_steps=next_steps,
    )


@router.delete("/remove")
async def remove_subdomain(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove subdomain configuration."""
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()

    if not config or not config.email_subdomain:
        raise HTTPException(status_code=400, detail="No subdomain configured")

    subdomain = config.email_subdomain

    # Clear subdomain configuration
    config.email_subdomain = None
    config.subdomain_verification_status = None
    config.subdomain_dns_records = None
    config.subdomain_verified_at = None
    config.subdomain_last_check_at = None
    config.subdomain_verification_token = None

    db.commit()

    logger.info(f"Subdomain removed for user {current_user.id}: {subdomain}")

    return {
        "success": True,
        "message": f"Subdomain {subdomain} has been removed. Emails will be sent from CleanEnroll's default domain.",
    }
