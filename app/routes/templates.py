import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..cache import cache
from ..database import get_db
from ..models import BusinessConfig, FormTemplate, User, UserTemplateCustomization

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])


def safe_get_sections(template_data: Optional[dict]) -> list[dict]:
    """Safely get sections from template_data, handling null values"""
    if template_data is None:
        return []
    return template_data.get("sections", [])


class FormFieldSchema(BaseModel):
    id: str
    label: str
    type: str
    placeholder: Optional[str] = None
    options: Optional[list[str]] = None
    required: Optional[bool] = False
    hint: Optional[str] = None
    accept: Optional[str] = None
    multiple: Optional[bool] = False
    maxFiles: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None
    sliderLabels: Optional[list[str]] = None
    uploadMode: Optional[str] = None


class FormSectionSchema(BaseModel):
    id: str
    title: str
    description: str
    fields: list[FormFieldSchema]


class FormTemplateSchema(BaseModel):
    id: str
    name: str
    description: str
    image: str
    color: str
    sections: list[FormSectionSchema]
    base_template_id: Optional[str] = None


class CreateTemplateRequest(BaseModel):
    template_id: str
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    color: Optional[str] = "#00C4B4"
    sections: list[FormSectionSchema]


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    color: Optional[str] = None
    sections: Optional[list[FormSectionSchema]] = None


@router.get("/", response_model=list[FormTemplateSchema])
async def get_templates(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all available templates for the current user (filtered by active templates) - with caching"""

    # Try to get from cache first
    cache_key = f"user_templates_{current_user.id}"
    cached_templates = cache.get(cache_key)

    if cached_templates is not None:
        logger.info(f"✅ Returning cached templates for user {current_user.email}")
        return cached_templates

    # Get user's business config to check active templates
    business_config = (
        db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    )

    # Get active template IDs
    active_template_ids = None
    if business_config and business_config.active_templates:
        active_template_ids = business_config.active_templates
        logger.info(f"🔍 User {current_user.email} has active templates: {active_template_ids}")
    else:
        logger.info(f"⚠️ User {current_user.email} has no active templates configured - showing all")
        logger.info(f"   - business_config exists: {business_config is not None}")
        if business_config:
            logger.info(f"   - active_templates value: {business_config.active_templates}")
            logger.info(f"   - active_templates type: {type(business_config.active_templates)}")
    # If no active templates configured, return all templates (backward compatibility)

    # Get system templates (pre-built)
    system_templates_query = db.query(FormTemplate).filter(
        FormTemplate.is_system_template, FormTemplate.is_active
    )

    # Filter by active templates if configured
    if active_template_ids:
        system_templates_query = system_templates_query.filter(
            FormTemplate.template_id.in_(active_template_ids)
        )
        logger.info(f"🎯 Filtering templates to: {active_template_ids}")

    system_templates = system_templates_query.all()
    logger.info(f"📋 Found {len(system_templates)} system templates after filtering")

    # Get user's custom templates (always include these)
    user_templates = (
        db.query(FormTemplate)
        .filter(FormTemplate.user_id == current_user.id, FormTemplate.is_active)
        .all()
    )

    # Get user's customizations
    customizations = (
        db.query(UserTemplateCustomization)
        .filter(
            UserTemplateCustomization.user_id == current_user.id,
            UserTemplateCustomization.is_active,
        )
        .all()
    )

    # Build response
    templates = []

    # Add system templates with user customizations if any
    for template in system_templates:
        template_data = template.template_data

        # Check if user has customizations for this template
        customization = next((c for c in customizations if c.template_id == template.id), None)
        if customization:
            template_data = customization.customized_data

        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template_data),
            )
        )

    # Add user's custom templates
    for template in user_templates:
        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template.template_data),
            )
        )

    # Cache the result for 5 minutes
    cache.set(cache_key, templates, ttl=300)

    logger.info(
        f"✅ Returning {len(templates)} total templates to user {current_user.email} (cached)"
    )
    return templates


@router.get("/{template_id}", response_model=FormTemplateSchema)
async def get_template(
    template_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get a specific template by ID"""
    # First check if it's a system template
    template = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == template_id,
            FormTemplate.is_system_template,
            FormTemplate.is_active,
        )
        .first()
    )

    if not template:
        # Check if it's a user's custom template
        template = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_id,
                FormTemplate.user_id == current_user.id,
                FormTemplate.is_active,
            )
            .first()
        )

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template_data = template.template_data

    # Check if user has customizations for this system template
    if template.is_system_template:
        customization = (
            db.query(UserTemplateCustomization)
            .filter(
                UserTemplateCustomization.user_id == current_user.id,
                UserTemplateCustomization.template_id == template.id,
                UserTemplateCustomization.is_active,
            )
            .first()
        )

        if customization:
            template_data = customization.customized_data

    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=safe_get_sections(template_data),
    )


@router.post("/", response_model=FormTemplateSchema)
async def create_template(
    request: CreateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new custom template"""
    # Check if template_id already exists for this user
    existing = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == request.template_id, FormTemplate.user_id == current_user.id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Template ID already exists"
        )

    # Create template data structure
    template_data = {"sections": [section.dict() for section in request.sections]}

    # Create new template
    template = FormTemplate(
        template_id=request.template_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        image=request.image,
        color=request.color,
        is_system_template=False,
        template_data=template_data,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    # Invalidate cache
    cache_key = f"user_templates_{current_user.id}"
    cache.delete(cache_key)
    logger.info(f"🗑️ Invalidated template cache for user {current_user.email}")

    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=safe_get_sections(template_data),
    )


@router.put("/{template_id}", response_model=FormTemplateSchema)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a template or create customization for system template"""
    # First check if it's a system template
    system_template = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == template_id,
            FormTemplate.is_system_template,
            FormTemplate.is_active,
        )
        .first()
    )

    if system_template:
        # This is a system template, create/update customization
        customization = (
            db.query(UserTemplateCustomization)
            .filter(
                UserTemplateCustomization.user_id == current_user.id,
                UserTemplateCustomization.template_id == system_template.id,
                UserTemplateCustomization.is_active,
            )
            .first()
        )

        # Build customized data - handle null template_data
        customized_data = (
            system_template.template_data.copy() if system_template.template_data else {}
        )
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
                customized_data=customized_data,
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

        # Invalidate cache
        cache_key = f"user_templates_{current_user.id}"
        cache.delete(cache_key)
        logger.info(f"🗑️ Invalidated template cache for user {current_user.email}")

        return FormTemplateSchema(
            id=system_template.template_id,
            name=system_template.name,
            description=system_template.description or "",
            image=system_template.image or "",
            color=system_template.color or "#00C4B4",
            sections=safe_get_sections(customized_data),
        )

    else:
        # Check if it's user's custom template
        template = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_id,
                FormTemplate.user_id == current_user.id,
                FormTemplate.is_active,
            )
            .first()
        )

        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

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
            template.template_data = {"sections": [section.dict() for section in request.sections]}

        db.commit()
        db.refresh(template)

        # Invalidate cache
        cache_key = f"user_templates_{current_user.id}"
        cache.delete(cache_key)
        logger.info(f"🗑️ Invalidated template cache for user {current_user.email}")

        return FormTemplateSchema(
            id=template.template_id,
            name=template.name,
            description=template.description or "",
            image=template.image or "",
            color=template.color or "#00C4B4",
            sections=safe_get_sections(template.template_data),
        )


@router.delete("/{template_id}")
async def delete_template(
    template_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete a custom template or remove customization for system template"""
    # First check if it's a system template customization
    system_template = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == template_id,
            FormTemplate.is_system_template,
            FormTemplate.is_active,
        )
        .first()
    )

    if system_template:
        # Remove user's customization for this system template
        customization = (
            db.query(UserTemplateCustomization)
            .filter(
                UserTemplateCustomization.user_id == current_user.id,
                UserTemplateCustomization.template_id == system_template.id,
                UserTemplateCustomization.is_active,
            )
            .first()
        )

        if customization:
            customization.is_active = False
            db.commit()

            # Invalidate cache
            cache_key = f"user_templates_{current_user.id}"
            cache.delete(cache_key)
            logger.info(f"🗑️ Invalidated template cache for user {current_user.email}")

        return {"message": "Template customization removed"}

    else:
        # Check if it's user's custom template
        template = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_id,
                FormTemplate.user_id == current_user.id,
                FormTemplate.is_active,
            )
            .first()
        )

        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        # Soft delete custom template
        template.is_active = False
        db.commit()

        # Invalidate cache
        cache_key = f"user_templates_{current_user.id}"
        cache.delete(cache_key)
        logger.info(f"🗑️ Invalidated template cache for user {current_user.email}")

        return {"message": "Template deleted"}


# Custom domain-aware endpoints for secure template access
@router.get("/domain/templates", response_model=list[FormTemplateSchema])
async def get_templates_by_domain(request: Request, db: Session = Depends(get_db)):
    """Get all templates for a business via custom domain (secure) - filtered by active templates"""
    # Check if this is a custom domain request
    if not hasattr(request.state, "is_custom_domain") or not request.state.is_custom_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available via custom domains",
        )

    if not hasattr(request.state, "custom_domain_user_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Custom domain not configured properly"
        )

    user_id = request.state.custom_domain_user_id

    # Get user's business config to check active templates
    business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user_id).first()

    # Get active template IDs
    active_template_ids = None
    if business_config and business_config.active_templates:
        active_template_ids = business_config.active_templates
    # If no active templates configured, return all templates (backward compatibility)

    # Get system templates (pre-built)
    system_templates_query = db.query(FormTemplate).filter(
        FormTemplate.is_system_template, FormTemplate.is_active
    )

    # Filter by active templates if configured
    if active_template_ids:
        system_templates_query = system_templates_query.filter(
            FormTemplate.template_id.in_(active_template_ids)
        )

    system_templates = system_templates_query.all()

    # Get user's custom templates (always include these)
    user_templates = (
        db.query(FormTemplate).filter(FormTemplate.user_id == user_id, FormTemplate.is_active).all()
    )

    # Get user's customizations
    customizations = (
        db.query(UserTemplateCustomization)
        .filter(
            UserTemplateCustomization.user_id == user_id,
            UserTemplateCustomization.is_active,
        )
        .all()
    )

    # Build response
    templates = []

    # Add system templates with user customizations if any
    for template in system_templates:
        template_data = template.template_data

        # Check if user has customizations for this template
        customization = next((c for c in customizations if c.template_id == template.id), None)
        if customization:
            template_data = customization.customized_data

        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template_data),
            )
        )

    # Add user's custom templates
    for template in user_templates:
        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template.template_data),
            )
        )

    return templates


@router.get("/domain/templates/{template_id}", response_model=FormTemplateSchema)
async def get_template_by_domain(template_id: str, request: Request, db: Session = Depends(get_db)):
    """Get a template via custom domain (secure)"""
    # Check if this is a custom domain request
    if not hasattr(request.state, "is_custom_domain") or not request.state.is_custom_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available via custom domains",
        )

    if not hasattr(request.state, "custom_domain_user_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Custom domain not configured properly"
        )

    user_id = request.state.custom_domain_user_id

    # First check if it's a system template
    template = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == template_id,
            FormTemplate.is_system_template,
            FormTemplate.is_active,
        )
        .first()
    )

    if not template:
        # Check if it's a user's custom template
        template = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_id,
                FormTemplate.user_id == user_id,
                FormTemplate.is_active,
            )
            .first()
        )

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template_data = template.template_data

    # Check if user has customizations for this system template
    if template.is_system_template:
        customization = (
            db.query(UserTemplateCustomization)
            .filter(
                UserTemplateCustomization.user_id == user_id,
                UserTemplateCustomization.template_id == template.id,
                UserTemplateCustomization.is_active,
            )
            .first()
        )

        if customization:
            template_data = customization.customized_data

    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=safe_get_sections(template_data),
    )


# Public endpoints for client forms
@router.get("/public/{owner_uid}", response_model=list[FormTemplateSchema])
async def get_public_templates(owner_uid: str, request: Request, db: Session = Depends(get_db)):
    """Get all templates for a business (public access for embed/template selection) - filtered by active templates"""
    # If this is a custom domain request, validate that the domain belongs to the requested user
    if hasattr(request.state, "is_custom_domain") and request.state.is_custom_domain:
        if (
            not hasattr(request.state, "custom_domain_user_uid")
            or request.state.custom_domain_user_uid != owner_uid
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Custom domain does not match requested user",
            )

    # Find the user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == owner_uid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get user's business config to check active templates
    business_config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

    # Get active template IDs
    active_template_ids = None
    if business_config and business_config.active_templates:
        active_template_ids = business_config.active_templates
    # If no active templates configured, return all templates (backward compatibility)

    # Get system templates (pre-built)
    system_templates_query = db.query(FormTemplate).filter(
        FormTemplate.is_system_template, FormTemplate.is_active
    )

    # Filter by active templates if configured
    if active_template_ids:
        system_templates_query = system_templates_query.filter(
            FormTemplate.template_id.in_(active_template_ids)
        )

    system_templates = system_templates_query.all()

    # Get user's custom templates (always include these)
    user_templates = (
        db.query(FormTemplate).filter(FormTemplate.user_id == user.id, FormTemplate.is_active).all()
    )

    # Get user's customizations
    customizations = (
        db.query(UserTemplateCustomization)
        .filter(
            UserTemplateCustomization.user_id == user.id,
            UserTemplateCustomization.is_active,
        )
        .all()
    )

    # Build response
    templates = []

    # Add system templates with user customizations if any
    for template in system_templates:
        template_data = template.template_data

        # Check if user has customizations for this template
        customization = next((c for c in customizations if c.template_id == template.id), None)
        if customization:
            template_data = customization.customized_data

        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template_data),
            )
        )

    # Add user's custom templates
    for template in user_templates:
        templates.append(
            FormTemplateSchema(
                id=template.template_id,
                name=template.name,
                description=template.description or "",
                image=template.image or "",
                color=template.color or "#00C4B4",
                sections=safe_get_sections(template.template_data),
            )
        )

    return templates


@router.get("/public/{owner_uid}/{template_id}", response_model=FormTemplateSchema)
async def get_public_template(
    owner_uid: str, template_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get a template for public client form access"""
    # If this is a custom domain request, validate that the domain belongs to the requested user
    if hasattr(request.state, "is_custom_domain") and request.state.is_custom_domain:
        if (
            not hasattr(request.state, "custom_domain_user_uid")
            or request.state.custom_domain_user_uid != owner_uid
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Custom domain does not match requested user",
            )

    # Find the user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == owner_uid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # First check if it's a system template
    template = (
        db.query(FormTemplate)
        .filter(
            FormTemplate.template_id == template_id,
            FormTemplate.is_system_template,
            FormTemplate.is_active,
        )
        .first()
    )

    if not template:
        # Check if it's a user's custom template
        template = (
            db.query(FormTemplate)
            .filter(
                FormTemplate.template_id == template_id,
                FormTemplate.user_id == user.id,
                FormTemplate.is_active,
            )
            .first()
        )

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    template_data = template.template_data

    # Check if user has customizations for this system template
    if template.is_system_template:
        customization = (
            db.query(UserTemplateCustomization)
            .filter(
                UserTemplateCustomization.user_id == user.id,
                UserTemplateCustomization.template_id == template.id,
                UserTemplateCustomization.is_active,
            )
            .first()
        )

        if customization:
            template_data = customization.customized_data

    return FormTemplateSchema(
        id=template.template_id,
        name=template.name,
        description=template.description or "",
        image=template.image or "",
        color=template.color or "#00C4B4",
        sections=safe_get_sections(template_data),
    )
