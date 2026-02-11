import logging
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import boto3
from botocore.config import Config
from ..database import get_db
from ..models import User, BusinessConfig
from ..config import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

# Export R2_BUCKET_NAME for use in other modules
__all__ = ["router", "get_r2_client", "generate_presigned_url", "R2_BUCKET_NAME"]

# Presigned URL expiration time (1 hour)
PRESIGNED_URL_EXPIRATION = 3600

# Allowed image types for uploads
ALLOWED_IMAGE_TYPES = [
    "image/png",
    "image/jpeg",
    "image/jpg", 
    "image/webp",
    "image/svg+xml",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/x-icon",
    "image/vnd.microsoft.icon",
    "image/heic",
    "image/heif",
    "image/avif",
]

def get_r2_client():
    """Create and return an R2 client."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )

def generate_presigned_url(key: str, expiration: int = PRESIGNED_URL_EXPIRATION) -> str:
    """Generate a presigned URL for accessing a private object in R2."""
    r2 = get_r2_client()
    
    # Add response content type for SVG files to ensure proper rendering
    params = {"Bucket": R2_BUCKET_NAME, "Key": key}
    
    # If it's an SVG file, ensure it's served with the correct content type
    if key.lower().endswith('.svg'):
        params["ResponseContentType"] = "image/svg+xml"
        params["ResponseContentDisposition"] = "inline"
    
    # For image files, set proper content type and disposition
    if any(key.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic', '.heif', '.avif']):
        params["ResponseContentDisposition"] = "inline"
    
    try:
        url = r2.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expiration,
        )
        logger.info(f"✅ Generated presigned URL for key: {key}")
        return url
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL for key {key}: {e}")
        raise

@router.post("/logo/{firebase_uid}")
async def upload_logo(
    firebase_uid: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload business logo to R2 (private)."""
    logger.info(f"📤 Uploading logo for firebase_uid: {firebase_uid}")
    # Validate firebase_uid format to prevent path traversal
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Allowed image types for business logos
    LOGO_IMAGE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
        "image/svg+xml",
    ]

    # Validate file type
    if file.content_type not in LOGO_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PNG, JPEG, WebP, GIF, and SVG images are allowed."
        )

    # Validate filename to prevent path traversal
    if file.filename:
        logger.info(f"🔍 Validating filename: '{file.filename}'")
        
        # Check for path traversal attempts and dangerous characters
        dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            if char in file.filename:
                logger.warning(f"❌ Dangerous character '{char}' detected in filename: '{file.filename}'")
                raise HTTPException(status_code=400, detail=f"Invalid filename - contains dangerous character '{char}'")
        
        # Ensure filename has a valid extension
        valid_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg')
        if not file.filename.lower().endswith(valid_extensions):
            logger.warning(f"❌ Invalid extension in filename: '{file.filename}'")
            raise HTTPException(status_code=400, detail="Invalid filename - must have a valid image extension")
        
        # Check filename length (reasonable limit)
        if len(file.filename) > 255:
            logger.warning(f"❌ Filename too long: '{file.filename}' ({len(file.filename)} chars)")
            raise HTTPException(status_code=400, detail="Filename too long - maximum 255 characters")
    # Read file contents
    contents = await file.read()
    
    # Validate file size (5MB = 5 * 1024 * 1024 bytes)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds 5MB limit. Your file is {len(contents) / (1024 * 1024):.2f}MB."
        )

    # Generate unique filename (store the key, not the URL)
    ext = file.filename.split(".")[-1] if file.filename else "png"
    key = f"logos/{firebase_uid}/{uuid.uuid4()}.{ext}"

    try:
        r2 = get_r2_client()

        # Set appropriate content type and metadata for SVG files
        put_object_params = {
            "Bucket": R2_BUCKET_NAME,
            "Key": key,
            "Body": contents,
            "ContentType": file.content_type,
        }
        
        # Add specific metadata for SVG files to ensure proper handling
        if file.content_type == "image/svg+xml":
            put_object_params["ContentDisposition"] = "inline"
            put_object_params["CacheControl"] = "public, max-age=31536000"  # 1 year cache
        
        r2.put_object(**put_object_params)

        # Store the key (not URL) in database
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if config:
            config.logo_url = key  # Store key, not URL
            db.commit()

        # Return presigned URL for immediate display
        presigned_url = generate_presigned_url(key)
        return {"url": presigned_url, "key": key}

    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/signature/{firebase_uid}")
async def upload_signature(
    firebase_uid: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload signature image to R2 (private)."""
    logger.info(f"📤 Uploading signature for firebase_uid: {firebase_uid}")

    # Validate firebase_uid format to prevent path traversal
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image file.")

    # Validate filename to prevent path traversal
    if file.filename:
        import os
        safe_filename = os.path.basename(file.filename)
        if safe_filename != file.filename or '..' in file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

    # Generate unique filename (store the key, not the URL)
    ext = file.filename.split(".")[-1] if file.filename else "png"
    key = f"signatures/{firebase_uid}/{uuid.uuid4()}.{ext}"

    try:
        r2 = get_r2_client()
        contents = await file.read()

        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=file.content_type,
        )

        # Store the key (not URL) in database
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if config:
            config.signature_url = key  # Store key, not URL
            db.commit()

        # Return presigned URL for immediate display
        presigned_url = generate_presigned_url(key)
        return {"url": presigned_url, "key": key}

    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/presigned/{firebase_uid}/{file_type}")
async def get_presigned_url_endpoint(
    firebase_uid: str,
    file_type: str,
    db: Session = Depends(get_db),
):
    """Get a presigned URL for an existing file (logo, signature, or profile-picture)."""
    # Validate firebase_uid format to prevent path traversal
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid user identifier")
    
    # Validate file_type to prevent injection
    allowed_file_types = ["logo", "signature", "profile-picture"]
    if file_type not in allowed_file_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Use one of: {', '.join(allowed_file_types)}")
    
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if file_type == "profile-picture":
        key = user.profile_picture_url
    else:
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Business config not found")

        if file_type == "logo":
            key = config.logo_url
        elif file_type == "signature":
            key = config.signature_url
        else:
            raise HTTPException(status_code=400, detail="Invalid file type. Use 'logo', 'signature', or 'profile-picture'.")

    if not key:
        raise HTTPException(status_code=404, detail=f"No {file_type} found")

    try:
        presigned_url = generate_presigned_url(key)
        return {"url": presigned_url}
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")

@router.post("/profile-picture/{firebase_uid}")
async def upload_profile_picture(
    firebase_uid: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload user profile picture to R2 (private)."""
    logger.info(f"📤 Uploading profile picture for firebase_uid: {firebase_uid}")

    # Validate firebase_uid format to prevent path traversal
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Allowed image types for profile pictures
    PROFILE_PICTURE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
    ]

    # Validate file type
    if file.content_type not in PROFILE_PICTURE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only PNG, JPEG, WebP, and GIF images are allowed."
        )

    # Validate filename to prevent path traversal
    if file.filename:
        import os
        safe_filename = os.path.basename(file.filename)
        if safe_filename != file.filename or '..' in file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

    # Read file contents
    contents = await file.read()
    
    # Validate file size (5MB = 5 * 1024 * 1024 bytes)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds 5MB limit. Your file is {len(contents) / (1024 * 1024):.2f}MB."
        )

    # Generate unique filename
    ext = file.filename.split(".")[-1] if file.filename else "png"
    key = f"profile-pictures/{firebase_uid}/{uuid.uuid4()}.{ext}"

    try:
        r2 = get_r2_client()

        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=file.content_type,
        )

        # Store the key in user record
        user.profile_picture_url = key
        db.commit()

        # Return presigned URL for immediate display
        presigned_url = generate_presigned_url(key)
        return {"url": presigned_url, "key": key}

    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/integration-logo")
async def upload_integration_logo(
    file: UploadFile = File(...),
):
    """Upload integration request logo to R2 (public access for display)."""
    logger.info(f"📤 Uploading integration logo: {file.filename}")

    # Allowed image types for integration logos
    LOGO_IMAGE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
        "image/svg+xml",
    ]

    # Validate file type
    if file.content_type not in LOGO_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PNG, JPEG, WebP, GIF, and SVG images are allowed."
        )

    # Validate filename to prevent path traversal
    if file.filename:
        import os
        safe_filename = os.path.basename(file.filename)
        if safe_filename != file.filename or '..' in file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

    # Read file contents
    contents = await file.read()
    
    # Validate file size (2MB limit for integration logos)
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds 2MB limit. Your file is {len(contents) / (1024 * 1024):.2f}MB."
        )

    # Generate unique filename
    ext = file.filename.split(".")[-1] if file.filename else "png"
    key = f"integration-logos/{uuid.uuid4()}.{ext}"

    try:
        r2 = get_r2_client()

        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=file.content_type,
        )

        # Return presigned URL for display and key for storage
        presigned_url = generate_presigned_url(key, expiration=86400 * 7)  # 7 days
        return {"url": presigned_url, "key": key}

    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
