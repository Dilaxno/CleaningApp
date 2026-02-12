from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import User, BusinessConfig
from ..auth import get_current_user

router = APIRouter(prefix="/template-selection", tags=["template-selection"])

# Pre-built template definitions (matching frontend templates.ts)
AVAILABLE_TEMPLATES = [
    {
        "id": "office",
        "name": "Office / Building",
        "description": "Professional cleaning for offices and commercial spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/commercial_office_jf1pvb.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "retail",
        "name": "Retail Store",
        "description": "Keep your store spotless for customers.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/retail_store_h567sp.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "medical",
        "name": "Medical / Dental Clinic",
        "description": "Specialized cleaning for healthcare facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087509/Medical_Clinic_rnq02h.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "gym",
        "name": "Fitness Gym / Studio",
        "description": "Keep your gym fresh and clean.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087510/gym_uhy5i9.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "restaurant",
        "name": "Restaurant / Cafe",
        "description": "Professional cleaning for food service.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087529/cafe_vlqstf.webp",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "school",
        "name": "School / Daycare",
        "description": "Safe cleaning for educational facilities.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/school_opn4hw.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "warehouse",
        "name": "Warehouse / Industrial",
        "description": "Heavy-duty cleaning for industrial spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/warehouse_korsp2.jpg",
        "color": "#1a1a1a",
        "category": "🏢 Commercial"
    },
    {
        "id": "residential",
        "name": "Residential / Home",
        "description": "Professional home cleaning services.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/residential_aoijhw.jpg",
        "color": "#1a1a1a",
        "category": "🏠 Residential"
    },
    {
        "id": "airbnb",
        "name": "Airbnb / Short-Term Rental",
        "description": "Turnover cleaning for vacation rentals.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/Airbnb_qopjpn.jpg",
        "color": "#1a1a1a",
        "category": "🏠 Residential"
    },
    {
        "id": "move-in-out",
        "name": "Move In / Move Out",
        "description": "Deep cleaning for property transitions.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087527/Move_in_Move_out_srjbid.webp",
        "color": "#1a1a1a",
        "category": "🏠 Residential"
    },
    {
        "id": "deep-clean",
        "name": "Deep Clean",
        "description": "Comprehensive deep cleaning services.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770038049/deep_clean_tvl1an.jpg",
        "color": "#1a1a1a",
        "category": "🏠 Residential"
    },
    {
        "id": "post-construction",
        "name": "Post-Construction",
        "description": "Specialized cleanup after construction work.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1768087528/post_construction_uqr9kl.jpg",
        "color": "#1a1a1a",
        "category": "🏗 Specialty"
    },
    {
        "id": "outside-cleaning",
        "name": "Outside Cleaning",
        "description": "Exterior cleaning services for buildings and outdoor spaces.",
        "image": "https://res.cloudinary.com/dxqum9ywx/image/upload/v1770247865/outside_cleaning_acgpg4.jpg",
        "color": "#1a1a1a",
        "category": "🏗 Specialty"
    },
    {
        "id": "carpet-cleaning",
        "name": "Carpet Cleaning",
        "description": "Professional carpet and upholstery cleaning services.",
        "image": "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80",
        "color": "#1a1a1a",
        "category": "🏗 Specialty"
    }
]

class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    image: str
    color: str
    category: str

class TemplateSelectionResponse(BaseModel):
    templates: List[TemplateInfo]
    categories: List[str]

class UpdateActiveTemplatesRequest(BaseModel):
    activeTemplates: List[str]

@router.get("/debug-auth")
async def debug_auth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to test authentication"""
    return {
        "message": "Authentication successful",
        "user_id": current_user.id,
        "email": current_user.email,
        "firebase_uid": current_user.firebase_uid
    }

@router.get("/available", response_model=TemplateSelectionResponse)
async def get_available_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available templates for selection during onboarding"""
    
    # Group templates by category
    categories = list(set(template["category"] for template in AVAILABLE_TEMPLATES))
    categories.sort()
    
    templates = [TemplateInfo(**template) for template in AVAILABLE_TEMPLATES]
    
    return TemplateSelectionResponse(
        templates=templates,
        categories=categories
    )

@router.get("/active", response_model=List[str])
async def get_active_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current user's active template IDs"""
    
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config or not business_config.active_templates:
        # Return all templates by default for backward compatibility
        return [template["id"] for template in AVAILABLE_TEMPLATES]
    
    return business_config.active_templates

@router.post("/active")
async def update_active_templates(
    request: UpdateActiveTemplatesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the user's active template selection"""
    
    # Validate that all provided template IDs exist
    valid_template_ids = {template["id"] for template in AVAILABLE_TEMPLATES}
    invalid_ids = set(request.activeTemplates) - valid_template_ids
    
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template IDs: {', '.join(invalid_ids)}"
        )
    
    # Get or create business config
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not business_config:
        # Create new business config if it doesn't exist
        business_config = BusinessConfig(
            user_id=current_user.id,
            active_templates=request.activeTemplates
        )
        db.add(business_config)
    else:
        # Update existing config
        business_config.active_templates = request.activeTemplates
    
    db.commit()
    
    return {"message": "Active templates updated successfully"}

@router.get("/filtered/{owner_uid}")
async def get_filtered_templates_for_client(
    owner_uid: str,
    db: Session = Depends(get_db)
):
    """Get filtered templates for client form selection (public endpoint)"""
    
    # Find the user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == owner_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get business config to check active templates
    business_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == user.id
    ).first()
    
    active_template_ids = []
    if business_config and business_config.active_templates:
        active_template_ids = business_config.active_templates
    else:
        # If no active templates configured, return all templates (backward compatibility)
        active_template_ids = [template["id"] for template in AVAILABLE_TEMPLATES]
    
    # Filter templates based on active selection
    filtered_templates = [
        TemplateInfo(**template) 
        for template in AVAILABLE_TEMPLATES 
        if template["id"] in active_template_ids
    ]
    
    return {
        "templates": filtered_templates,
        "total": len(filtered_templates)
    }