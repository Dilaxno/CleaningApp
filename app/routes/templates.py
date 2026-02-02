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
        },
        "retail": {
            "id": "retail",
            "name": "Retail Store",
            "description": "Keep your store spotless for customers.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "businessName", "label": "Store name", "type": "text", "placeholder": "ABC Retail Store", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@store.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Store address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Store Details",
                    "description": "Tell us about your retail space.",
                    "fields": [
                        {"id": "squareFootage", "label": "Store square footage", "type": "number", "placeholder": "3000", "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "storeType", "label": "Type of retail store", "type": "select", "options": ["Clothing", "Electronics", "Grocery", "Pharmacy", "Department Store", "Specialty Shop", "Other"], "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "floorTypes", "label": "Main floor type", "type": "select", "options": ["Tile", "Hardwood", "Carpet", "Vinyl", "Concrete", "Mixed"], "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of customer restrooms", "type": "number", "placeholder": "2", "required": False, "order": 9, "enabled": True, "locked": False},
                        {"id": "hasChangingRooms", "label": "Do you have changing rooms?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Traffic/Dirty", "Moderate Clean", "Light Maintenance"], "required": True, "hint": "This helps us estimate the time and effort needed", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly", "One-time deep clean"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "operatingHours", "label": "Store operating hours", "type": "text", "placeholder": "9 AM - 9 PM", "required": False, "hint": "When is your store open?", "order": 13, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["Before opening", "After closing", "During business hours", "Flexible"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 16, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 17, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Store photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 18, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or notes?", "type": "textarea", "placeholder": "Window cleaning, floor waxing, specific product requirements, etc.", "required": False, "order": 19, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "medical": {
            "id": "medical",
            "name": "Medical / Dental Clinic",
            "description": "Specialized cleaning for healthcare facilities.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "Dr. Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "facilityName", "label": "Facility name", "type": "text", "placeholder": "ABC Medical Center", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "admin@clinic.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Medical Dr, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Facility Details",
                    "description": "Tell us about your medical facility.",
                    "fields": [
                        {"id": "facilityType", "label": "Type of medical facility", "type": "select", "options": ["General Practice", "Dental Office", "Specialist Clinic", "Urgent Care", "Physical Therapy", "Veterinary Clinic", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Facility square footage", "type": "number", "placeholder": "2500", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "numberOfExamRooms", "label": "Number of exam/treatment rooms", "type": "number", "placeholder": "6", "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "3", "required": False, "order": 9, "enabled": True, "locked": False},
                        {"id": "hasWaitingArea", "label": "Do you have a waiting area?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Deep Sanitization Needed", "Standard Medical Clean", "Light Maintenance"], "required": True, "hint": "Medical facilities require specialized cleaning protocols", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "One-time deep clean"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "operatingHours", "label": "Facility operating hours", "type": "text", "placeholder": "8 AM - 6 PM", "required": False, "hint": "When is your facility open?", "order": 13, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["Before opening", "After closing", "During lunch break", "Weekends only"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "requiresDisinfection", "label": "Do you require medical-grade disinfection?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Medical facilities typically require specialized disinfection protocols", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Facility photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or compliance requirements?", "type": "textarea", "placeholder": "HIPAA compliance, specific disinfectants, biohazard disposal, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "restaurant": {
            "id": "restaurant",
            "name": "Restaurant / Cafe",
            "description": "Professional cleaning for food service establishments.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "restaurantName", "label": "Restaurant name", "type": "text", "placeholder": "ABC Restaurant", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "manager@restaurant.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Restaurant address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Restaurant Details",
                    "description": "Tell us about your establishment.",
                    "fields": [
                        {"id": "restaurantType", "label": "Type of establishment", "type": "select", "options": ["Fine Dining", "Casual Dining", "Fast Food", "Cafe/Coffee Shop", "Bar/Pub", "Food Truck", "Catering Kitchen", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Total square footage", "type": "number", "placeholder": "2000", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "seatingCapacity", "label": "Seating capacity", "type": "number", "placeholder": "50", "required": False, "order": 8, "enabled": True, "locked": False},
                        {"id": "hasKitchen", "label": "Do you have a commercial kitchen?", "type": "radio", "options": ["Yes", "No"], "required": True, "order": 9, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of customer restrooms", "type": "number", "placeholder": "2", "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Deep Clean Needed", "Standard Restaurant Clean", "Light Maintenance"], "required": True, "hint": "Food service requires specialized cleaning protocols", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "One-time deep clean"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "operatingHours", "label": "Restaurant operating hours", "type": "text", "placeholder": "11 AM - 10 PM", "required": False, "hint": "When is your restaurant open?", "order": 13, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["Before opening", "After closing", "During closed hours", "Early morning"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "requiresKitchenCleaning", "label": "Do you need kitchen deep cleaning?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Kitchen cleaning requires specialized equipment and training", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Restaurant photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or health code requirements?", "type": "textarea", "placeholder": "Grease trap cleaning, hood cleaning, health department compliance, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "gym": {
            "id": "gym",
            "name": "Fitness Gym / Studio",
            "description": "Keep your gym fresh and clean.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "gymName", "label": "Gym/Studio name", "type": "text", "placeholder": "ABC Fitness Center", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "manager@gym.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Fitness St, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Facility Details",
                    "description": "Tell us about your fitness facility.",
                    "fields": [
                        {"id": "facilityType", "label": "Type of fitness facility", "type": "select", "options": ["Full Service Gym", "Boutique Studio", "CrossFit Box", "Yoga Studio", "Dance Studio", "Martial Arts Dojo", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Facility square footage", "type": "number", "placeholder": "4000", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "hasLocker rooms", "label": "Do you have locker rooms?", "type": "radio", "options": ["Yes", "No"], "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "4", "required": False, "order": 9, "enabled": True, "locked": False},
                        {"id": "hasShowers", "label": "Do you have showers?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Deep Sanitization Needed", "Standard Gym Clean", "Light Maintenance"], "required": True, "hint": "Gyms require frequent sanitization due to high traffic", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "One-time deep clean"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "operatingHours", "label": "Gym operating hours", "type": "text", "placeholder": "5 AM - 11 PM", "required": False, "hint": "When is your gym open?", "order": 13, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["Before opening", "After closing", "During off-peak hours", "Overnight"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "requiresEquipmentSanitizing", "label": "Do you need equipment sanitizing?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Fitness equipment requires specialized cleaning", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Facility photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or requirements?", "type": "textarea", "placeholder": "Locker room deep cleaning, mirror cleaning, floor sanitization, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "airbnb": {
            "id": "airbnb",
            "name": "Airbnb / Short-Term Rental",
            "description": "Turnover cleaning for vacation rentals.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "propertyName", "label": "Property name", "type": "text", "placeholder": "Cozy Downtown Apartment", "required": False, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "host@email.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, Apt 2B, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Property Details",
                    "description": "Tell us about your rental property.",
                    "fields": [
                        {"id": "propertyType", "label": "Type of property", "type": "select", "options": ["Apartment", "House", "Condo", "Studio", "Loft", "Cabin", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Property square footage", "type": "number", "placeholder": "800", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "2", "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "1", "required": True, "order": 9, "enabled": True, "locked": False},
                        {"id": "maxGuests", "label": "Maximum number of guests", "type": "number", "placeholder": "4", "required": True, "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Typical turnover condition", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Cleanup Needed", "Standard Turnover", "Light Refresh"], "required": True, "hint": "This helps us estimate turnover time", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["After every guest", "Weekly", "Bi-weekly", "Monthly", "As needed"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "averageBookings", "label": "Average bookings per month", "type": "number", "placeholder": "8", "required": False, "hint": "This helps us plan availability", "order": 13, "enabled": True, "locked": False},
                        {"id": "turnaroundTime", "label": "Typical turnaround time between guests", "type": "select", "options": ["Same day", "Next day", "2-3 days", "Flexible"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "requiresLinenService", "label": "Do you need linen service?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "We can wash and change linens", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Property photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or amenities to maintain?", "type": "textarea", "placeholder": "Hot tub cleaning, restocking amenities, key management, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "school": {
            "id": "school",
            "name": "School / Daycare",
            "description": "Safe cleaning for educational facilities.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "Principal Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "schoolName", "label": "School/Facility name", "type": "text", "placeholder": "ABC Elementary School", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "admin@school.edu", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "School address", "type": "textarea", "placeholder": "123 Education St, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Facility Details",
                    "description": "Tell us about your educational facility.",
                    "fields": [
                        {"id": "facilityType", "label": "Type of educational facility", "type": "select", "options": ["Elementary School", "Middle School", "High School", "Daycare Center", "Preschool", "University", "Training Center", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Facility square footage", "type": "number", "placeholder": "15000", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "numberOfClassrooms", "label": "Number of classrooms", "type": "number", "placeholder": "20", "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "8", "required": False, "order": 9, "enabled": True, "locked": False},
                        {"id": "hasCafeteria", "label": "Do you have a cafeteria?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "hasGymnasium", "label": "Do you have a gymnasium?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 11, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Deep Sanitization Needed", "Standard School Clean", "Light Maintenance"], "required": True, "hint": "Schools require child-safe cleaning protocols", "order": 12, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "Summer deep clean"], "required": True, "order": 13, "enabled": True, "locked": False},
                        {"id": "schoolHours", "label": "School operating hours", "type": "text", "placeholder": "8 AM - 3 PM", "required": False, "hint": "When are students present?", "order": 14, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["After school hours", "Evenings", "Weekends", "During breaks"], "required": True, "order": 15, "enabled": True, "locked": False},
                        {"id": "requiresChildSafeProducts", "label": "Do you require child-safe cleaning products?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Child-safe, non-toxic products are recommended for schools", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 17, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 18, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 19, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Facility photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 20, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or safety requirements?", "type": "textarea", "placeholder": "Playground cleaning, child safety protocols, allergy considerations, etc.", "required": False, "order": 21, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "warehouse": {
            "id": "warehouse",
            "name": "Warehouse / Industrial",
            "description": "Heavy-duty cleaning for industrial spaces.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "companyName", "label": "Company name", "type": "text", "placeholder": "ABC Logistics", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "manager@company.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Facility address", "type": "textarea", "placeholder": "123 Industrial Blvd, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Facility Details",
                    "description": "Tell us about your industrial facility.",
                    "fields": [
                        {"id": "facilityType", "label": "Type of industrial facility", "type": "select", "options": ["Warehouse", "Manufacturing Plant", "Distribution Center", "Storage Facility", "Workshop", "Factory", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Facility square footage", "type": "number", "placeholder": "50000", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "ceilingHeight", "label": "Ceiling height (feet)", "type": "number", "placeholder": "20", "required": False, "order": 8, "enabled": True, "locked": False},
                        {"id": "floorType", "label": "Main floor type", "type": "select", "options": ["Concrete", "Epoxy", "Sealed Concrete", "Industrial Tile", "Other"], "required": True, "order": 9, "enabled": True, "locked": False},
                        {"id": "numberOfRestrooms", "label": "Number of restrooms", "type": "number", "placeholder": "4", "required": False, "order": 10, "enabled": True, "locked": False},
                        {"id": "hasOfficeSpace", "label": "Do you have office space?", "type": "radio", "options": ["Yes", "No"], "required": False, "order": 11, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current cleanliness level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Industrial Clean", "Standard Warehouse Clean", "Light Maintenance"], "required": True, "hint": "Industrial facilities require specialized equipment", "order": 12, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningFrequency", "label": "How often do you need cleaning?", "type": "select", "options": ["Daily", "3x per week", "Weekly", "Bi-weekly", "Monthly", "Quarterly"], "required": True, "order": 13, "enabled": True, "locked": False},
                        {"id": "operatingHours", "label": "Facility operating hours", "type": "text", "placeholder": "6 AM - 6 PM", "required": False, "hint": "When is your facility operational?", "order": 14, "enabled": True, "locked": False},
                        {"id": "preferredServiceTime", "label": "Preferred cleaning time", "type": "select", "options": ["After hours", "Weekends", "During downtime", "Flexible"], "required": True, "order": 15, "enabled": True, "locked": False},
                        {"id": "requiresHeavyEquipment", "label": "Do you need heavy-duty equipment cleaning?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Industrial cleaning may require specialized equipment", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "12", "required": False, "hint": "How long should this contract last?", "order": 17, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Months", "Years"], "required": False, "order": 18, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 19, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Facility photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 20, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or safety requirements?", "type": "textarea", "placeholder": "High-pressure washing, degreasing, safety protocols, hazardous material handling, etc.", "required": False, "order": 21, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "post-construction": {
            "id": "post-construction",
            "name": "Post-Construction",
            "description": "Deep cleaning after construction or renovation.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "companyName", "label": "Company/Project name", "type": "text", "placeholder": "ABC Construction", "required": False, "order": 2, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "project@company.com", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 4, "enabled": True, "locked": False},
                        {"id": "address", "label": "Project address", "type": "textarea", "placeholder": "123 Construction St, City, State ZIP", "required": True, "order": 5, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Project Details",
                    "description": "Tell us about your construction project.",
                    "fields": [
                        {"id": "projectType", "label": "Type of construction project", "type": "select", "options": ["New Construction", "Renovation", "Remodel", "Addition", "Commercial Build-out", "Restoration", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Project square footage", "type": "number", "placeholder": "3000", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "constructionPhase", "label": "Construction phase", "type": "select", "options": ["Rough Construction Complete", "Final Phase", "Move-in Ready", "Touch-ups Remaining"], "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "floorTypes", "label": "Floor types installed", "type": "select", "options": ["Hardwood", "Tile", "Carpet", "Vinyl", "Concrete", "Mixed"], "required": True, "order": 9, "enabled": True, "locked": False},
                        {"id": "hasWindows", "label": "Do you need window cleaning?", "type": "radio", "options": ["Yes", "No"], "required": True, "order": 10, "enabled": True, "locked": False},
                        {"id": "debrisLevel", "label": "Construction debris level", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Heavy Debris/Dust", "Moderate Cleanup", "Light Finishing Clean"], "required": True, "hint": "This helps us estimate the cleanup effort needed", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningType", "label": "Type of post-construction cleaning", "type": "select", "options": ["Rough Clean", "Final Clean", "Touch-up Clean", "Complete Package"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "projectDeadline", "label": "Project completion deadline", "type": "date", "required": False, "hint": "When do you need the cleaning completed?", "order": 13, "enabled": True, "locked": False},
                        {"id": "accessAvailability", "label": "Site access availability", "type": "select", "options": ["24/7 Access", "Business Hours Only", "Weekends Only", "Scheduled Access"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "requiresSpecialEquipment", "label": "Do you need specialized equipment?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "High-reach cleaning, pressure washing, etc.", "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "1", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Weeks", "Months"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Project photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or requirements?", "type": "textarea", "placeholder": "Paint removal, adhesive cleanup, fixture cleaning, specific safety requirements, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        },
        "move-in-out": {
            "id": "move-in-out",
            "name": "Move In / Move Out",
            "description": "Deep cleaning for moving transitions.",
            "sections": [
                {
                    "id": "client-info",
                    "title": "Contact Information",
                    "description": "Let's start with your details.",
                    "fields": [
                        {"id": "contactName", "label": "Your name", "type": "text", "placeholder": "John Smith", "required": True, "order": 1, "enabled": True, "locked": False},
                        {"id": "email", "label": "Email address", "type": "email", "placeholder": "john@email.com", "required": True, "order": 2, "enabled": True, "locked": False},
                        {"id": "phone", "label": "Phone number", "type": "tel", "placeholder": "(555) 123-4567", "required": True, "order": 3, "enabled": True, "locked": False},
                        {"id": "address", "label": "Property address", "type": "textarea", "placeholder": "123 Main St, City, State ZIP", "required": True, "order": 4, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "property-details",
                    "title": "Property Details",
                    "description": "Tell us about the property.",
                    "fields": [
                        {"id": "moveType", "label": "Type of move", "type": "select", "options": ["Move Out Cleaning", "Move In Cleaning", "Both (Move Out + Move In)"], "required": True, "order": 5, "enabled": True, "locked": False},
                        {"id": "propertyType", "label": "Property type", "type": "select", "options": ["Apartment", "House", "Condo", "Townhouse", "Other"], "required": True, "order": 6, "enabled": True, "locked": False},
                        {"id": "squareFootage", "label": "Property square footage", "type": "number", "placeholder": "1500", "required": True, "order": 7, "enabled": True, "locked": False},
                        {"id": "bedrooms", "label": "Number of bedrooms", "type": "number", "placeholder": "3", "required": True, "order": 8, "enabled": True, "locked": False},
                        {"id": "bathrooms", "label": "Number of bathrooms", "type": "number", "placeholder": "2", "required": True, "order": 9, "enabled": True, "locked": False},
                        {"id": "moveDate", "label": "Move date", "type": "date", "required": True, "hint": "When do you need the cleaning completed?", "order": 10, "enabled": True, "locked": False},
                        {"id": "cleanlinessLevel", "label": "Current condition of property", "type": "slider", "min": 1, "max": 3, "sliderLabels": ["Needs Deep Cleaning", "Standard Condition", "Well Maintained"], "required": True, "hint": "This helps us estimate the cleaning effort needed", "order": 11, "enabled": True, "locked": False},
                    ]
                },
                {
                    "id": "service-requirements",
                    "title": "Service Needs",
                    "description": "What cleaning services do you need?",
                    "fields": [
                        {"id": "cleaningScope", "label": "Cleaning scope", "type": "select", "options": ["Basic Move Out/In Clean", "Deep Clean", "Premium Clean with Details"], "required": True, "order": 12, "enabled": True, "locked": False},
                        {"id": "includesAppliances", "label": "Clean inside appliances?", "type": "radio", "options": ["Yes", "No"], "required": True, "hint": "Refrigerator, oven, microwave interior cleaning", "order": 13, "enabled": True, "locked": False},
                        {"id": "includesCabinets", "label": "Clean inside cabinets and drawers?", "type": "radio", "options": ["Yes", "No"], "required": True, "order": 14, "enabled": True, "locked": False},
                        {"id": "timeFlexibility", "label": "Time flexibility", "type": "select", "options": ["Specific date required", "Within 2-3 days", "Within a week", "Flexible"], "required": True, "order": 15, "enabled": True, "locked": False},
                        {"id": "contractTermDuration", "label": "Contract term duration", "type": "number", "placeholder": "1", "required": False, "hint": "How long should this contract last?", "order": 16, "enabled": True, "locked": False},
                        {"id": "contractTermUnit", "label": "Contract term unit", "type": "select", "options": ["Weeks", "Months"], "required": False, "order": 17, "enabled": True, "locked": False},
                        {"id": "selectedAddons", "label": "Would you like any add-on services?", "type": "addons", "required": False, "hint": "Select any additional services you'd like", "order": 18, "enabled": True, "locked": True},
                        {"id": "propertyShots", "label": "Property photos (optional)", "type": "file", "required": False, "accept": "image/*", "multiple": True, "maxFiles": 10, "uploadMode": "client-r2", "hint": "Upload photos to help set clear expectations. Please only film/photograph the property (no people). Your images are private and are only shared with the cleaning business.", "order": 19, "enabled": True, "locked": False},
                        {"id": "specialRequests", "label": "Any special requests or areas of focus?", "type": "textarea", "placeholder": "Pet odor removal, stain treatment, specific areas that need extra attention, etc.", "required": False, "order": 20, "enabled": True, "locked": True},
                    ]
                }
            ]
        }
        # All templates are now complete
    }
    
    if base_template_id not in templates:
        raise HTTPException(status_code=404, detail="Base template not found")
    
    return templates[base_template_id]