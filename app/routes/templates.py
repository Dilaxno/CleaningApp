from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import FormTemplate, User, UserTemplateCustomization
from ..auth import get_current_user


router = APIRouter(prefix="/templates", tags=["templates"])


class FormFieldSchema(BaseModel):
    id: str
    label: str
    type: str
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None
    required: Optional[bool] = False
    hint: Optional[str] = None
    accept: Optional[str] = None
    multiple: Optional[bool] = False
    maxFiles: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None
    sliderLabels: Optional[List[str]] = None
    uploadMode: Optional[str] = None


class FormSectionSchema(BaseModel):
    id: str
    title: str
    description: str
    fields: List[FormFieldSchema]


class FormTemplateSchema(BaseModel):
    id: str
    name: str
    description: str
    image: str
    color: str
    sections: List[FormSectionSchema]
    base_template_id: Optional[str] = None


class CreateTemplateRequest(BaseModel):
    template_id: str
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    color: Optional[str] = "#00C4B4"
    sections: List[FormSectionSchema]


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    color: Optional[str] = None
    sections: Optional[List[FormSectionSchema]] = None


@router.get("/", response_model=List[FormTemplateSchema])
async def get_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available templates for the current user"""
    # Get system templates (pre-built)
    system_templates = db.query(FormTemplate).filter(
        FormTemplate.is_system_template == True,
        FormTemplate.is_active == True
    ).all()
    
    # Get user's custom templates
    user_templates = db.query(FormTemplate).filter(
        FormTemplate.user_id == current_user.id,
        FormTemplate.is_active == True
    ).all()
    
    # Get user's customizations
    customizations = db.query(UserTemplateCustomization).filter(
        UserTemplateCustomization.user_id == current_user.id,
        UserTemplateCustomization.is_active == True
    ).all()
    
    # Build response
    templates = []
    
    # Add system templates with user customizations if any
    for template in system_templates:
        template_data = template.template_data
        
        # Check if user has customizations for this template
        customization = next(
            (c for c in customizations if c.template_id == template.id), 
            None
        )
        if customization:
            template_data = customization.customized_data
        
        templates.append(FormTemplateSchema(
            id=template.template_id,
            name=template.name,
            description=template.description or "",
            image=template.image or "",
            color=template.color or "#00C4B4",
            sections=template_data.get("sections", [])
        ))
    
    # Add user's custom templates
    for template in user_templates:
        templates.append(FormTemplateSchema(
            id=template.template_id,
            name=template.name,
            description=template.description or "",
            image=template.image or "",
            color=template.color or "#00C4B4",
            sections=template.template_data.get("sections", [])
        ))
    
    return templates


@router.get("/{template_id}", response_model=FormTemplateSchema)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific template by ID"""
    # First check if it's a system template
    template = db.query(FormTemplate).filter(
        FormTemplate.template_id == template_id,
        FormTemplate.is_system_template == True,
        FormTemplate.is_active == True
    ).first()
    
    if not template:
        # Check if it's a user's custom template
        template = db.query(FormTemplate).filter(
            FormTemplate.template_id == template_id,
            FormTemplate.user_id == current_user.id,
            FormTemplate.is_active == True
        ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    template_data = template.template_data
    
    # Check if user has customizations for this system template
    if template.is_system_template:
        customization = db.query(UserTemplateCustomization).filter(
            UserTemplateCustomization.user_id == current_user.id,
            UserTemplateCustomization.template_id == template.id,
            UserTemplateCustomization.is_active == True
        ).first()
        
        if customization:
            template_data = customization.customized_data
    
    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=template_data.get("sections", [])
    )


@router.post("/", response_model=FormTemplateSchema)
async def create_template(
    request: CreateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new custom template"""
    # Check if template_id already exists for this user
    existing = db.query(FormTemplate).filter(
        FormTemplate.template_id == request.template_id,
        FormTemplate.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template ID already exists"
        )
    
    # Create template data structure
    template_data = {
        "sections": [section.dict() for section in request.sections]
    }
    
    # Create new template
    template = FormTemplate(
        template_id=request.template_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        image=request.image,
        color=request.color,
        is_system_template=False,
        template_data=template_data
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=template_data.get("sections", [])
    )


@router.put("/{template_id}", response_model=FormTemplateSchema)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a template or create customization for system template"""
    # First check if it's a system template
    system_template = db.query(FormTemplate).filter(
        FormTemplate.template_id == template_id,
        FormTemplate.is_system_template == True,
        FormTemplate.is_active == True
    ).first()
    
    if system_template:
        # This is a system template, create/update customization
        customization = db.query(UserTemplateCustomization).filter(
            UserTemplateCustomization.user_id == current_user.id,
            UserTemplateCustomization.template_id == system_template.id,
            UserTemplateCustomization.is_active == True
        ).first()
        
        # Build customized data
        customized_data = system_template.template_data.copy()
        if request.sections:
            customized_data["sections"] = [section.dict() for section in request.sections]
        
        if customization:
            # Update existing customization
            customization.customized_data = customized_data
        else:
            # Create new customization
            customization = UserTemplateCustomization(
                user_id=current_user.id,
                template_id=system_template.id,
                customized_data=customized_data
            )
            db.add(customization)
        
        db.commit()
        
        # Update system template metadata if provided
        if request.name:
            system_template.name = request.name
        if request.description:
            system_template.description = request.description
        if request.image:
            system_template.image = request.image
        if request.color:
            system_template.color = request.color
        
        db.commit()
        db.refresh(system_template)
        
        return FormTemplateSchema(
            id=system_template.template_id,
            name=system_template.name,
            description=system_template.description or "",
            image=system_template.image or "",
            color=system_template.color or "#00C4B4",
            sections=customized_data.get("sections", [])
        )
    
    else:
        # Check if it's user's custom template
        template = db.query(FormTemplate).filter(
            FormTemplate.template_id == template_id,
            FormTemplate.user_id == current_user.id,
            FormTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Update custom template
        if request.name:
            template.name = request.name
        if request.description:
            template.description = request.description
        if request.image:
            template.image = request.image
        if request.color:
            template.color = request.color
        if request.sections:
            template.template_data = {
                "sections": [section.dict() for section in request.sections]
            }
        
        db.commit()
        db.refresh(template)
        
        return FormTemplateSchema(
            id=template.template_id,
            name=template.name,
            description=template.description or "",
            image=template.image or "",
            color=template.color or "#00C4B4",
            sections=template.template_data.get("sections", [])
        )


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a custom template or remove customization for system template"""
    # First check if it's a system template customization
    system_template = db.query(FormTemplate).filter(
        FormTemplate.template_id == template_id,
        FormTemplate.is_system_template == True,
        FormTemplate.is_active == True
    ).first()
    
    if system_template:
        # Remove user's customization for this system template
        customization = db.query(UserTemplateCustomization).filter(
            UserTemplateCustomization.user_id == current_user.id,
            UserTemplateCustomization.template_id == system_template.id,
            UserTemplateCustomization.is_active == True
        ).first()
        
        if customization:
            customization.is_active = False
            db.commit()
        
        return {"message": "Template customization removed"}
    
    else:
        # Check if it's user's custom template
        template = db.query(FormTemplate).filter(
            FormTemplate.template_id == template_id,
            FormTemplate.user_id == current_user.id,
            FormTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Soft delete custom template
        template.is_active = False
        db.commit()
        
        return {"message": "Template deleted"}


# Public endpoints for client forms
@router.get("/public/{owner_uid}/{template_id}", response_model=FormTemplateSchema)
async def get_public_template(
    owner_uid: str,
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a template for public client form access"""
    # Find the user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == owner_uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # First check if it's a system template
    template = db.query(FormTemplate).filter(
        FormTemplate.template_id == template_id,
        FormTemplate.is_system_template == True,
        FormTemplate.is_active == True
    ).first()
    
    if not template:
        # Check if it's a user's custom template
        template = db.query(FormTemplate).filter(
            FormTemplate.template_id == template_id,
            FormTemplate.user_id == user.id,
            FormTemplate.is_active == True
        ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    template_data = template.template_data
    
    # Check if user has customizations for this system template
    if template.is_system_template:
        customization = db.query(UserTemplateCustomization).filter(
            UserTemplateCustomization.user_id == user.id,
            UserTemplateCustomization.template_id == template.id,
            UserTemplateCustomization.is_active == True
        ).first()
        
        if customization:
            template_data = customization.customized_data
    
    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=template_data.get("sections", [])
    )