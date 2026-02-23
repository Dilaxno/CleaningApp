import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IntakeToken

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/embed", tags=["embed"])


class CreateIntakeTokenRequest(BaseModel):
    business_id: str
    template_id: str
    full_name: str
    email: EmailStr
    phone: str


class CreateIntakeTokenResponse(BaseModel):
    token: str


@router.post("/create-intake-token", response_model=CreateIntakeTokenResponse)
async def create_intake_token(
    request: CreateIntakeTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Create a secure token for pre-intake form data transfer.
    This token will be used to securely pass client information from the
    pre-intake form to the full intake form without exposing sensitive data in URLs.
    """
    try:
        # Generate a secure random token
        token = secrets.token_urlsafe(32)

        # Create token record with 1-hour expiration
        intake_token = IntakeToken(
            token=token,
            business_id=request.business_id,
            template_id=request.template_id,
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used=False,
        )

        db.add(intake_token)
        db.commit()

        logger.info(
            f"✅ Created intake token for {request.email} (business: {request.business_id})"
        )

        return CreateIntakeTokenResponse(token=token)

    except Exception as e:
        logger.error(f"❌ Failed to create intake token: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create intake session",
        )


class GetIntakeDataResponse(BaseModel):
    full_name: str
    email: str
    phone: str
    template_id: str


@router.get("/intake-data/{token}", response_model=GetIntakeDataResponse)
async def get_intake_data(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve pre-intake form data using a secure token.
    This endpoint is called by the full intake form to pre-fill client information.
    The token can only be used once and expires after 1 hour.
    """
    try:
        # Find the token
        intake_token = db.query(IntakeToken).filter(IntakeToken.token == token).first()

        if not intake_token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired token",
            )

        # Check if token is expired
        if intake_token.expires_at < datetime.utcnow():
            db.delete(intake_token)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token has expired",
            )

        # Check if token was already used
        if intake_token.used:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token has already been used",
            )

        # Mark token as used
        intake_token.used = True
        db.commit()

        logger.info(f"✅ Retrieved intake data for token (email: {intake_token.email})")

        return GetIntakeDataResponse(
            full_name=intake_token.full_name,
            email=intake_token.email,
            phone=intake_token.phone,
            template_id=intake_token.template_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve intake data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve intake data",
        )
