"""
Service Areas API Routes

Handles service area configuration and ZIP code validation.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..services.service_area_validator import ServiceAreaValidator
from ..rate_limiter import create_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/service-areas", tags=["service-areas"])

# Rate limiters for service area endpoints
rate_limit_api = create_rate_limiter(limit=100, window_seconds=60, key_prefix="service_areas_api")
rate_limit_validation = create_rate_limiter(limit=20, window_seconds=60, key_prefix="zipcode_validation")


class ServiceArea(BaseModel):
    """Service area configuration model."""
    type: str = Field(..., description="Type: state, county, neighborhood, or city")
    value: str = Field(..., description="Area identifier (state code, county name, city name)")
    name: str = Field(..., description="Display name for the area")
    state: Optional[str] = Field(None, description="State code (required for county/neighborhood)")
    county: Optional[str] = Field(None, description="County name (required for neighborhood)")


class ServiceAreasUpdate(BaseModel):
    """Request model for updating service areas."""
    service_areas: List[ServiceArea] = Field(..., description="List of service areas")


class ServiceAreasResponse(BaseModel):
    """Response model for service areas."""
    service_areas: List[ServiceArea]


class ZipCodeValidationRequest(BaseModel):
    """Request model for ZIP code validation."""
    zipcode: str = Field(..., description="ZIP code to validate", min_length=5, max_length=10)
    business_uid: str = Field(..., description="Business owner Firebase UID")


class ZipCodeValidationResponse(BaseModel):
    """Response model for ZIP code validation."""
    valid: bool = Field(..., description="Whether ZIP code is in service area")
    message: Optional[str] = Field(None, description="Error or informational message")


@router.get("/", response_model=ServiceAreasResponse)
async def get_service_areas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Get configured service areas for the current business."""
    try:
        validator = ServiceAreaValidator(db)
        service_areas = validator.get_service_areas_for_business(current_user.firebase_uid)
        
        # Convert to Pydantic models
        areas = []
        for area in service_areas:
            areas.append(ServiceArea(**area))
        
        return ServiceAreasResponse(service_areas=areas)
        
    except Exception as e:
        logger.error(f"Error getting service areas for user {current_user.firebase_uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service areas")


@router.put("/", response_model=ServiceAreasResponse)
async def update_service_areas(
    request: ServiceAreasUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Update service areas for the current business."""
    try:
        # Convert Pydantic models to dict
        service_areas_data = []
        for area in request.service_areas:
            area_dict = area.dict(exclude_none=True)
            service_areas_data.append(area_dict)
        
        validator = ServiceAreaValidator(db)
        success = validator.update_service_areas_for_business(
            current_user.firebase_uid, 
            service_areas_data
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Invalid service area configuration")
        
        # Return updated service areas
        updated_areas = validator.get_service_areas_for_business(current_user.firebase_uid)
        areas = []
        for area in updated_areas:
            areas.append(ServiceArea(**area))
        
        return ServiceAreasResponse(service_areas=areas)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating service areas for user {current_user.firebase_uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update service areas")


@router.post("/validate-zipcode", response_model=ZipCodeValidationResponse)
async def validate_zipcode(
    request: ZipCodeValidationRequest,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_validation),
):
    """
    Validate if a ZIP code is within a business's service areas.
    Public endpoint for client form access validation.
    """
    try:
        validator = ServiceAreaValidator(db)
        is_valid, message = validator.validate_zipcode_for_business(
            request.zipcode, 
            request.business_uid
        )
        
        return ZipCodeValidationResponse(valid=is_valid, message=message)
        
    except Exception as e:
        logger.error(f"Error validating ZIP code {request.zipcode} for business {request.business_uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate ZIP code")


@router.get("/states")
async def get_us_states():
    """Get list of US states for service area configuration."""
    from ..services.service_area_validator import US_STATES
    
    states = []
    for code, name in US_STATES.items():
        states.append({"code": code, "name": name})
    
    # Sort by name
    states.sort(key=lambda x: x["name"])
    
    return {"states": states}