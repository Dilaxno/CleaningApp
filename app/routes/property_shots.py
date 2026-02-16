"""Public upload + signed URL access for client-submitted property photos.

Security goals:
- Objects stored in PRIVATE R2 bucket.
- Upload is public (no auth) but requires a valid ownerUid (Firebase UID) and is rate-limited upstream.
- View is done through short-lived presigned URLs, accessible only to the authenticated business owner.

We store only the R2 object keys in the client's form_data (JSON).
"""

import logging
import mimetypes
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import R2_BUCKET_NAME
from ..database import get_db
from ..models import Client, User
from .upload import generate_presigned_url, get_r2_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def _safe_segment(value: str, max_len: int = 80) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = value.strip("-")
    return value[:max_len] or "na"


def _validate_owner_uid(owner_uid: str) -> None:
    # Basic sanity. Firebase UIDs are usually urlsafe-ish.
    if not owner_uid or len(owner_uid) > 200:
        raise HTTPException(status_code=400, detail="Invalid ownerUid")
    if ".." in owner_uid or "/" in owner_uid or "\\" in owner_uid:
        raise HTTPException(status_code=400, detail="Invalid ownerUid")


class PropertyShotUploadResponse(BaseModel):
    key: str


class VideoWalkthroughUploadResponse(BaseModel):
    key: str


@router.post("/public/video-walkthrough", response_model=VideoWalkthroughUploadResponse)
async def upload_video_walkthrough_public(
    file: UploadFile = File(...),
    ownerUid: str = Form(...),
    fieldId: str = Form("virtualWalkthrough"),
    templateId: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Public endpoint for uploading virtual walkthrough videos.

    Uploads a single video to the PRIVATE R2 bucket and returns its object key.
    """

    _validate_owner_uid(ownerUid)

    # Validate that business exists
    user = db.query(User).filter(User.firebase_uid == ownerUid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content_type = (file.content_type or "").lower()
    
    # Accept video MIME types
    allowed_video_types = {
        "video/mp4",
        "video/quicktime",  # .mov
        "video/x-msvideo",  # .avi
        "video/x-matroska",  # .mkv
        "video/webm",
    }
    
    if not content_type.startswith("video/") and content_type not in allowed_video_types:
        raise HTTPException(status_code=400, detail="Only video uploads are allowed (MP4, MOV, AVI, MKV, WebM)")

    # Limit size (250MB default for videos)
    max_bytes = int(os.getenv("VIDEO_WALKTHROUGH_MAX_BYTES", "262144000"))  # 250MB
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail="Video too large (max 250MB)")

    # Determine extension
    ext = os.path.splitext(file.filename)[1].lower()

    allowed_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    
    if not ext:
        guessed = mimetypes.guess_extension(content_type) or ".mp4"
        ext = (guessed or ".mp4").lower()

    if ext not in allowed_exts:
        if content_type in allowed_video_types:
            ext = (mimetypes.guess_extension(content_type) or ".mp4").lower()
        else:
            raise HTTPException(status_code=400, detail="Unsupported video type")

    # Final guard
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Unsupported video type")

    # Build key
    safe_template = _safe_segment(templateId or "intake")
    safe_field = _safe_segment(fieldId or "virtualWalkthrough")
    key = f"video-walkthroughs/{ownerUid}/{safe_template}/{safe_field}/{uuid.uuid4().hex}{ext}"

    try:
        r2 = get_r2_client()
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=content_type,
            ACL="private",
        )
        logger.info(f"✅ Uploaded video walkthrough: {key} ({len(contents)} bytes)")
        return VideoWalkthroughUploadResponse(key=key)
    except Exception as e:
        logger.error(f"❌ Failed to upload video walkthrough: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload video") from e


@router.post("/public/property-shot", response_model=PropertyShotUploadResponse)
async def upload_property_shot_public(
    file: UploadFile = File(...),
    ownerUid: str = Form(...),
    fieldId: str = Form("propertyShots"),
    templateId: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Public endpoint used by the embedded/client intake form.

    Uploads a single image to the PRIVATE R2 bucket and returns its object key.

    NOTE: This endpoint intentionally does NOT accept arbitrary content types.
    """

    _validate_owner_uid(ownerUid)

    # Validate that business exists
    user = db.query(User).filter(User.firebase_uid == ownerUid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed")

    # Limit size (10MB default)
    max_bytes = int(os.getenv("PROPERTY_SHOT_MAX_BYTES", "10485760"))
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    # Determine extension
    ext = os.path.splitext(file.filename)[1].lower()

    # Accept common image MIME types even if the filename extension is missing or uncommon.
    # Some devices/browsers upload HEIC/HEIF/AVIF with unexpected extensions or none at all.
    allowed_exts = {
        ".jpg",
        ".jpeg",
        ".jfif",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".avif",
    }
    allowed_content_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/tiff",
        "image/heic",
        "image/heif",
        "image/avif",
    }

    if not ext:
        guessed = mimetypes.guess_extension(content_type) or ".jpg"
        ext = (guessed or ".jpg").lower()

    # If the extension is unknown but the MIME type is a supported image type,
    # we still accept it and pick a safe extension based on the MIME type.
    if ext not in allowed_exts:
        if content_type in allowed_content_types:
            ext = (mimetypes.guess_extension(content_type) or ".jpg").lower()
            # mimetypes may return '.jpe' for image/jpeg
            if ext == ".jpe":
                ext = ".jpg"
        else:
            raise HTTPException(status_code=400, detail="Unsupported image type")

    # Final guard
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    # Build key
    safe_template = _safe_segment(templateId or "intake")
    safe_field = _safe_segment(fieldId or "propertyShots")
    key = f"property-shots/{ownerUid}/{safe_template}/{safe_field}/" f"{uuid.uuid4().hex}{ext}"

    try:
        r2 = get_r2_client()
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=content_type,
            # Keep private. (R2 defaults to private, but be explicit for S3 compatibility)
            ACL="private",
        )
        return PropertyShotUploadResponse(key=key)
    except Exception as e:
        logger.error(f"❌ Failed to upload property shot: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image") from e


class PropertyShotSignedUrlRequest(BaseModel):
    clientId: int
    key: str


class PropertyShotSignedUrlResponse(BaseModel):
    url: str


@router.post("/property-shots/signed-url", response_model=PropertyShotSignedUrlResponse)
async def get_property_shot_signed_url(
    payload: PropertyShotSignedUrlRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authenticated endpoint for the business owner to get a signed URL.

    Ensures the requested object key belongs to the requesting user's client.
    """

    logger.info(f"🔍 Fetching signed URL for client {payload.clientId}, key: {payload.key}")

    client = (
        db.query(Client)
        .filter(Client.id == payload.clientId, Client.user_id == current_user.id)
        .first()
    )
    if not client:
        logger.warning(f"❌ Client {payload.clientId} not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Client not found")

    form_data = client.form_data or {}
    allowed_keys = form_data.get("propertyShots") or []

    if isinstance(allowed_keys, str):
        allowed_keys = [allowed_keys]

    logger.info(f"📋 Allowed keys for client {payload.clientId}: {allowed_keys}")

    if payload.key not in allowed_keys:
        logger.warning(f"❌ Key {payload.key} not in allowed keys for client {payload.clientId}")
        raise HTTPException(status_code=403, detail="Not authorized for this image")

    try:
        url = generate_presigned_url(payload.key, expiration=3600)  # 1 hour
        logger.info(f"✅ Generated signed URL for client {payload.clientId}, key: {payload.key}")
        return PropertyShotSignedUrlResponse(url=url)
    except Exception as e:
        logger.error(
            f"❌ Failed to generate signed URL for client {payload.clientId}, key {payload.key}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to generate signed URL") from e



class VirtualWalkthroughUploadResponse(BaseModel):
    key: str


@router.post("/public/virtual-walkthrough", response_model=VirtualWalkthroughUploadResponse)
async def upload_virtual_walkthrough_public(
    file: UploadFile = File(...),
    ownerUid: str = Form(...),
    templateId: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Public endpoint for uploading virtual walkthrough videos.

    Uploads a single video to the PRIVATE R2 bucket and returns its object key.
    """

    _validate_owner_uid(ownerUid)

    # Validate that business exists
    user = db.query(User).filter(User.firebase_uid == ownerUid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video uploads are allowed")

    # Limit size (250MB default for videos)
    max_bytes = int(os.getenv("VIRTUAL_WALKTHROUGH_MAX_BYTES", "262144000"))  # 250MB
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail="Video too large (max 250MB)")

    # Determine extension
    ext = os.path.splitext(file.filename)[1].lower()

    # Accept common video formats
    allowed_exts = {
        ".mp4",
        ".mov",
        ".avi",
        ".webm",
        ".mkv",
        ".m4v",
    }
    allowed_content_types = {
        "video/mp4",
        "video/quicktime",
        "video/x-msvideo",
        "video/webm",
        "video/x-matroska",
        "video/x-m4v",
    }

    if not ext:
        guessed = mimetypes.guess_extension(content_type) or ".mp4"
        ext = (guessed or ".mp4").lower()

    # If the extension is unknown but the MIME type is a supported video type
    if ext not in allowed_exts:
        if content_type in allowed_content_types:
            ext = (mimetypes.guess_extension(content_type) or ".mp4").lower()
        else:
            raise HTTPException(status_code=400, detail="Unsupported video type")

    # Final guard
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Unsupported video type")

    # Build key
    safe_template = _safe_segment(templateId or "intake")
    key = f"virtual-walkthroughs/{ownerUid}/{safe_template}/{uuid.uuid4().hex}{ext}"

    try:
        r2 = get_r2_client()
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=content_type,
            ACL="private",
        )
        logger.info(f"✅ Uploaded virtual walkthrough: {key}")
        return VirtualWalkthroughUploadResponse(key=key)
    except Exception as e:
        logger.error(f"❌ Failed to upload virtual walkthrough: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload video") from e


class VirtualWalkthroughSignedUrlRequest(BaseModel):
    clientId: int
    key: str


class VirtualWalkthroughSignedUrlResponse(BaseModel):
    url: str


@router.post("/virtual-walkthrough/signed-url", response_model=VirtualWalkthroughSignedUrlResponse)
async def get_virtual_walkthrough_signed_url(
    payload: VirtualWalkthroughSignedUrlRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authenticated endpoint for the business owner to get a signed URL for virtual walkthrough video."""

    logger.info(f"🔍 Fetching signed URL for virtual walkthrough - client {payload.clientId}, key: {payload.key}")

    client = (
        db.query(Client)
        .filter(Client.id == payload.clientId, Client.user_id == current_user.id)
        .first()
    )
    if not client:
        logger.warning(f"❌ Client {payload.clientId} not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Client not found")

    form_data = client.form_data or {}
    allowed_key = form_data.get("virtualWalkthrough")

    if not allowed_key or payload.key != allowed_key:
        logger.warning(f"❌ Key {payload.key} not authorized for client {payload.clientId}")
        raise HTTPException(status_code=403, detail="Not authorized for this video")

    try:
        # Generate longer expiration for videos (2 hours)
        url = generate_presigned_url(payload.key, expiration=7200)
        logger.info(f"✅ Generated signed URL for virtual walkthrough - client {payload.clientId}")
        return VirtualWalkthroughSignedUrlResponse(url=url)
    except Exception as e:
        logger.error(
            f"❌ Failed to generate signed URL for virtual walkthrough - client {payload.clientId}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to generate signed URL") from e
