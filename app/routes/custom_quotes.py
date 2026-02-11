"""
Custom Quote Request API Routes
Handles video upload, quote submission, and approval flow
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
import json

from ..database import get_db
from ..models import CustomQuoteRequest, Client, User, Contract
from ..schemas import (
    CustomQuoteRequestCreate,
    CustomQuoteRequestResponse,
    CustomQuoteSubmission,
    CustomQuoteApproval,
    MessageResponse,
)
from ..auth import get_current_user
from ..utils.video_storage import (
    validate_video_file,
    generate_video_r2_key,
    upload_video_to_r2,
    generate_presigned_video_url,
    delete_video_from_r2,
)
from ..email_service import send_email

router = APIRouter(prefix="/api/custom-quote-requests", tags=["custom_quotes"])


@router.post("/upload", response_model=CustomQuoteRequestResponse, status_code=201)
async def upload_custom_quote_video(
    request: Request,
    client_id: int = Form(...),
    video: UploadFile = File(...),
    video_duration_seconds: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Client uploads a video walkthrough for custom quote request.
    Public endpoint - no authentication required (client-facing).
    """
    # Get client and validate
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Read video file
    video_content = await video.read()
    video_size = len(video_content)
    
    # Validate video
    is_valid, error_msg = validate_video_file(
        filename=video.filename,
        size_bytes=video_size,
        mime_type=video.content_type,
        duration_seconds=video_duration_seconds,
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Generate R2 key
    r2_key = generate_video_r2_key(
        user_id=client.user_id,
        client_id=client_id,
        filename=video.filename,
    )
    
    # Upload to R2
    metadata = {
        "client_id": str(client_id),
        "user_id": str(client.user_id),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    
    upload_success = upload_video_to_r2(
        file_content=video_content,
        r2_key=r2_key,
        mime_type=video.content_type,
        metadata=metadata,
    )
    
    if not upload_success:
        raise HTTPException(status_code=500, detail="Failed to upload video")
    
    # Create custom quote request record
    custom_quote_request = CustomQuoteRequest(
        user_id=client.user_id,
        client_id=client_id,
        video_r2_key=r2_key,
        video_filename=video.filename,
        video_size_bytes=video_size,
        video_duration_seconds=video_duration_seconds,
        video_mime_type=video.content_type,
        client_ip=request.client.host if request.client else None,
        client_user_agent=request.headers.get("user-agent"),
        status="pending",
    )
    
    db.add(custom_quote_request)
    db.commit()
    db.refresh(custom_quote_request)
    
    # Send notification email to provider
    provider = db.query(User).filter(User.id == client.user_id).first()
    if provider and provider.email and provider.notify_new_clients:
        try:
            from ..email_service import send_custom_quote_request_notification
            
            await send_custom_quote_request_notification(
                provider_email=provider.email,
                provider_name=provider.full_name or "Provider",
                client_name=client.business_name,
                client_email=client.email or "",
                client_phone=client.phone,
                property_type=client.property_type or "Property",
                property_size=client.property_size or 0,
                frequency=client.frequency or "One-time",
                video_duration=video_duration_seconds or 0,
                request_public_id=custom_quote_request.public_id,
            )
        except Exception as e:
            print(f"Failed to send email notification: {e}")
    
    # Return response with client details
    response_data = CustomQuoteRequestResponse.from_orm(custom_quote_request)
    response_data.client = {
        "id": client.id,
        "business_name": client.business_name,
        "contact_name": client.contact_name,
        "email": client.email,
        "phone": client.phone,
        "property_type": client.property_type,
        "property_size": client.property_size,
        "frequency": client.frequency,
    }
    
    return response_data


@router.get("", response_model=List[CustomQuoteRequestResponse])
def list_custom_quote_requests(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider lists all custom quote requests.
    Optionally filter by status.
    """
    query = db.query(CustomQuoteRequest).filter(
        CustomQuoteRequest.user_id == current_user.id
    ).options(joinedload(CustomQuoteRequest.client))
    
    if status:
        query = query.filter(CustomQuoteRequest.status == status)
    
    requests = query.order_by(CustomQuoteRequest.created_at.desc()).all()
    
    # Add client details to response
    response_list = []
    for req in requests:
        response_data = CustomQuoteRequestResponse.from_orm(req)
        if req.client:
            response_data.client = {
                "id": req.client.id,
                "business_name": req.client.business_name,
                "contact_name": req.client.contact_name,
                "email": req.client.email,
                "phone": req.client.phone,
                "property_type": req.client.property_type,
                "property_size": req.client.property_size,
                "frequency": req.client.frequency,
            }
        response_list.append(response_data)
    
    return response_list


@router.get("/{public_id}", response_model=CustomQuoteRequestResponse)
def get_custom_quote_request(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get specific custom quote request details.
    """
    request = (
        db.query(CustomQuoteRequest)
        .filter(
            CustomQuoteRequest.public_id == public_id,
            CustomQuoteRequest.user_id == current_user.id,
        )
        .options(joinedload(CustomQuoteRequest.client))
        .first()
    )
    
    if not request:
        raise HTTPException(status_code=404, detail="Custom quote request not found")
    
    response_data = CustomQuoteRequestResponse.from_orm(request)
    if request.client:
        response_data.client = {
            "id": request.client.id,
            "business_name": request.client.business_name,
            "contact_name": request.client.contact_name,
            "email": request.client.email,
            "phone": request.client.phone,
            "property_type": request.client.property_type,
            "property_size": request.client.property_size,
            "frequency": request.client.frequency,
            "form_data": request.client.form_data,
        }
    
    return response_data


@router.get("/{public_id}/video-url")
def get_video_url(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a presigned URL for video access.
    URL expires in 15 minutes.
    """
    request = db.query(CustomQuoteRequest).filter(
        CustomQuoteRequest.public_id == public_id,
        CustomQuoteRequest.user_id == current_user.id,
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Custom quote request not found")
    
    video_url = generate_presigned_video_url(request.video_r2_key, expiration_minutes=15)
    
    if not video_url:
        raise HTTPException(status_code=500, detail="Failed to generate video URL")
    
    return {
        "video_url": video_url,
        "expires_in_minutes": 15,
        "filename": request.video_filename,
        "size_bytes": request.video_size_bytes,
        "duration_seconds": request.video_duration_seconds,
    }


@router.post("/{public_id}/quote", response_model=CustomQuoteRequestResponse)
def submit_custom_quote(
    public_id: str,
    quote_data: CustomQuoteSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider submits a custom quote for the request.
    """
    request = db.query(CustomQuoteRequest).filter(
        CustomQuoteRequest.public_id == public_id,
        CustomQuoteRequest.user_id == current_user.id,
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Custom quote request not found")
    
    if request.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit quote for request with status: {request.status}"
        )
    
    # Update request with quote details
    request.custom_quote_amount = quote_data.custom_quote_amount
    request.custom_quote_description = quote_data.custom_quote_description
    request.custom_quote_notes = quote_data.custom_quote_notes
    request.expires_at = quote_data.expires_at
    request.quoted_at = datetime.utcnow()
    request.status = "quoted"
    
    if quote_data.custom_quote_line_items:
        request.custom_quote_line_items = [
            item.dict() for item in quote_data.custom_quote_line_items
        ]
    
    db.commit()
    db.refresh(request)
    
    # Send email to client
    client = db.query(Client).filter(Client.id == request.client_id).first()
    if client and client.email:
        try:
            from ..email_service import send_custom_quote_ready_notification
            from ..models import BusinessConfig
            
            # Get business config for email settings
            business_config = db.query(BusinessConfig).filter(
                BusinessConfig.user_id == current_user.id
            ).first()
            
            business_name = business_config.business_name if business_config else current_user.full_name or "Your cleaning provider"
            
            await send_custom_quote_ready_notification(
                client_email=client.email,
                client_name=client.contact_name or client.business_name,
                business_name=business_name,
                quote_amount=quote_data.custom_quote_amount,
                quote_description=quote_data.custom_quote_description,
                quote_notes=quote_data.custom_quote_notes,
                request_public_id=public_id,
                business_config=business_config,
            )
        except Exception as e:
            print(f"Failed to send quote email: {e}")
    
    return CustomQuoteRequestResponse.from_orm(request)


@router.post("/{public_id}/approve", response_model=MessageResponse)
async def approve_custom_quote(
    public_id: str,
    approval_data: CustomQuoteApproval,
    db: Session = Depends(get_db),
):
    """
    Client approves or rejects the custom quote.
    Public endpoint - no authentication required (client-facing).
    """
    request = db.query(CustomQuoteRequest).filter(
        CustomQuoteRequest.public_id == public_id
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Custom quote request not found")
    
    if request.status != "quoted":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond to request with status: {request.status}"
        )
    
    # Update request with client response
    request.client_response = approval_data.client_response
    request.client_response_notes = approval_data.client_response_notes
    request.responded_at = datetime.utcnow()
    request.status = approval_data.client_response  # "approved" or "rejected"
    
    db.commit()
    
    # If approved, create contract (similar to automatic quote flow)
    if approval_data.client_response == "approved":
        client = db.query(Client).filter(Client.id == request.client_id).first()
        
        # Create contract from custom quote
        contract = Contract(
            user_id=request.user_id,
            client_id=request.client_id,
            title=f"Cleaning Service Agreement - {client.business_name}",
            description=request.custom_quote_description or "Custom cleaning service",
            contract_type="recurring" if client.frequency else "one-time",
            status="new",
            client_onboarding_status="pending_signature",
            total_value=request.custom_quote_amount,
            currency=request.custom_quote_currency,
            payment_terms="As agreed",
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)
        
        # Link contract to request
        request.contract_id = contract.id
        db.commit()
        
        # Send notification email to provider
        try:
            from ..email_service import send_custom_quote_approved_notification
            from ..models import BusinessConfig
            
            provider = db.query(User).filter(User.id == request.user_id).first()
            business_config = db.query(BusinessConfig).filter(
                BusinessConfig.user_id == request.user_id
            ).first()
            
            if provider and provider.email:
                await send_custom_quote_approved_notification(
                    provider_email=provider.email,
                    provider_name=provider.full_name or "Provider",
                    client_name=client.contact_name or client.business_name,
                    client_email=client.email or "",
                    quote_amount=request.custom_quote_amount,
                    client_response_notes=approval_data.client_response_notes,
                    business_config=business_config,
                )
        except Exception as e:
            print(f"Failed to send approval notification: {e}")
        
        return MessageResponse(
            message=f"Quote approved! Redirecting to contract signature. Contract ID: {contract.id}"
        )
    else:
        return MessageResponse(message="Quote rejected. Thank you for your response.")


@router.delete("/{public_id}", response_model=MessageResponse)
def delete_custom_quote_request(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Provider deletes a custom quote request and associated video.
    """
    request = db.query(CustomQuoteRequest).filter(
        CustomQuoteRequest.public_id == public_id,
        CustomQuoteRequest.user_id == current_user.id,
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Custom quote request not found")
    
    # Delete video from R2
    delete_video_from_r2(request.video_r2_key)
    
    # Delete database record
    db.delete(request)
    db.commit()
    
    return MessageResponse(message="Custom quote request deleted successfully")
