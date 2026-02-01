import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import CustomTemplate, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Templates"])


class FieldConfig(BaseModel):
    id: str
    label: str
    type: str
    required: bool = False
    order: int
    enabled: bool = True
    locked: bool = False  # Special fields that cannot be reordered
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    hint: Optional[str] = None
    accept: Optional[str] = None
    multiple: Optional[bool] = None
    maxFiles: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None
    sliderLabels: Optional[List[str]] = None
    uploadMode: Optional[str] = None


class SectionConfig(BaseModel):
    id: str
    title: str
    description: str
    fields: List[FieldConfig]


class TemplateConfig(BaseModel):
    sections: List[SectionConfig]


class CustomTemplateCreate(BaseModel):
    base_template_id: str
    name: str
    description: Optional[str] = None
    template_config: TemplateConfig


class CustomTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template_config: Optional[TemplateConfig] = None
    is_active: Optional[bool] = None


class CustomTemplateResponse(BaseModel):
    id: int
    base_template_id: str
    name: str
    description: Optional[str]
    template_config: TemplateConfig
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/custom", response_model=List[CustomTemplateResponse])
async def get_custom_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all custom templates for the current user"""
    templates = db.query(CustomTemplate).filter(
        CustomTemplate.user_id == current_user.id
    ).order_by(CustomTemplate.created_at.desc()).all()
    
    return templates


@router.get("/custom/{template_id}", response_model=CustomTemplateResponse)
async def get_custom_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific custom template"""
    template = db.query(CustomTemplate).filter(
        CustomTemplate.id == template_id,
        CustomTemplate.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.post("/custom", response_model=CustomTemplateResponse)
async def create_custom_template(
    template_data: CustomTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new custom template"""
    # Validate that base template exists (you might want to add this validation)
    valid_base_templates = [
        "residential", "office", "medical", "restaurant", "retail", 
        "gym", "airbnb", "school", "warehouse", "post-construction", "move-in-out"
    ]
    
    if template_data.base_template_id not in valid_base_templates:
        raise HTTPException(status_code=400, detail="Invalid base template ID")
    
    # Create the custom template
    custom_template = CustomTemplate(
        user_id=current_user.id,
        base_template_id=template_data.base_template_id,
        name=template_data.name,
        description=template_data.description,
        template_config=template_data.template_config.dict()
    )
    
    db.add(custom_template)
    db.commit()
    db.refresh(custom_template)
    
    logger.info(f"Created custom template {custom_template.id} for user {current_user.id}")
    
    return custom_template


@router.put("/custom/{template_id}", response_model=CustomTemplateResponse)
async def update_custom_template(
    template_id: int,
    template_data: CustomTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a custom template"""
    template = db.query(CustomTemplate).filter(
        CustomTemplate.id == template_id,
        CustomTemplate.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Update fields that were provided
    if template_data.name is not None:
        template.name = template_data.name
    if template_data.description is not None:
        template.description = template_data.description
    if template_data.template_config is not None:
        template.template_config = template_data.template_config.dict()
    if template_data.is_active is not None:
        template.is_active = template_data.is_active
    
    db.commit()
    db.refresh(template)
    
    logger.info(f"Updated custom template {template_id} for user {current_user.id}")
    
    return template


@router.delete("/custom/{template_id}")
async def delete_custom_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a custom template"""
    template = db.query(CustomTemplate).filter(
        CustomTemplate.id == template_id,
        CustomTemplate.user_id == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    logger.info(f"Deleted custom template {template_id} for user {current_user.id}")
    
    return {"message": "Template deleted successfully"}


@router.get("/public/{business_id}/templates")
async def get_public_custom_templates(
    business_id: str,
    db: Session = Depends(get_db)
):
    """Get active custom templates for a business (public endpoint for forms)"""
    # First get the user ID from the business firebase UID
    user = db.query(User).filter(User.firebase_uid == business_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Get active custom templates for this business
    templates = db.query(CustomTemplate).filter(
        CustomTemplate.user_id == user.id,
        CustomTemplate.is_active == True
    ).all()
    
    # Convert to public format (without internal IDs)
    public_templates = []
    for template in templates:
        public_templates.append({
            "id": f"custom_{template.id}",  # Prefix to distinguish from base templates
            "name": template.name,
            "description": template.description,
            "base_template_id": template.base_template_id,
            "sections": template.template_config.get("sections", [])
        })
    
    return public_templates


@router.get("/public/{business_id}/template/{template_id}")
async def get_public_template(
    business_id: str,
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific template for a business (public endpoint for forms)"""
    # First get the user ID from the business firebase UID
    user = db.query(User).filter(User.firebase_uid == business_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Check if it's a custom template (prefixed with custom_)
    if template_id.startswith("custom_"):
        custom_template_id = int(template_id.replace("custom_", ""))
        template = db.query(CustomTemplate).filter(
            CustomTemplate.id == custom_template_id,
            CustomTemplate.user_id == user.id,
            CustomTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(status_code=404, detail="Custom template not found")
        
        return {
            "id": template_id,
            "name": template.name,
            "description": template.description,
            "base_template_id": template.base_template_id,
            "sections": template.template_config.get("sections", []),
            "color": "#1a1a1a",  # Default color, could be customized later
            "image": ""  # Could be customized later
        }
    else:
        # Return base template info - this would need to be implemented
        # For now, return a 404 to indicate it should use the frontend templates
        raise HTTPException(status_code=404, detail="Use base template from frontend")


@router.get("/base/{base_template_id}/fields")
async def get_base_template_fields(
    base_template_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get the default fields for a base template to use as starting point for customization"""
    
    # Template definitions matching frontend templates.ts
    templates = {
        "office": {
            "id": "office",
            "name": "Office / Commercial",
            "description": "Professional cleaning for offices and commercial spaces.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "companyName", "label": "Company name", "type": "text", "placeholder": "Acme Corporation", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@acme.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, Suite 100, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Property Details",
                    "description": "Tell us about your space.",
                    "fields": [
                        {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "5000", "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "floorTypes", "label": "Main floor type", "type": "select", "options": ["Carpet", "Tile", "Hardwood", "Vinyl", "Mixed"], "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "4", "required": False, "order": 8, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Duty Clean", "Standard Clean", "Light Touch-Up"], "required": True, "hint": "This helps us estimate the time and effort needed", "order": 9, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time deep clean", "Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly"], "required": True, "order": 10, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 11, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 12, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["Morning", "Afternoon", "Evening", "After hours"], "required": True, "order": 13, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 14, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Property photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 15, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or notes?", "type": "textarea", "placeholder": "Eco-friendly products, specific areas of focus, etc.", "required": False, "order": 16, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "residential": {
            "id": "residential",
            "name": "Residential / Home",
            "description": "Professional home cleaning services.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "address", "label": "Home address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True, "order": 4, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Home Details",
                    "description": "Tell us about your home.",
                    "fields": [
                        {"id": "squareFootage", "label": "Approximate square footage", "type": "number", "placeholder": "2000", "required": True, "order": 5, "enabled": True, "locked": False},
                        {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3", "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "hasPets", "label": "Do you have pets?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 8, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "How would you rate the current cleanliness?", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Very Messy", "Moderately Dirty", "Lightly Cluttered"], "required": True, "hint": "This helps us estimate the time and effort needed", "order": 9, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["One-time deep clean", "Weekly", "Bi-weekly", "Monthly", "As needed"], "required": True, "order": 10, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 11, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 12, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred time", "type": "select", "options": ["Morning", "Afternoon", "Flexible"], "required": True, "order": 13, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 14, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Property photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 15, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests?", "type": "textarea", "placeholder": "Deep cleaning, specific rooms, eco-friendly products, etc.", "required": False, "order": 16, "enabled": True, "locked": True},
                    ]
                }
            ]
        }
        # Add more templates as needed - for now just showing office and residential as examples
    }
    
    if base_template_id not in templates:
        raise HTTPException(status_code=404, detail="Base template not found")
    
    return templates[base_template_id]