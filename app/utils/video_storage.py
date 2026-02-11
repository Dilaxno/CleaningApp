"""
Video storage utilities for custom quote requests.
Handles video upload to R2, signed URL generation, and validation.
"""

import boto3
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Tuple
from botocore.client import Config
from botocore.exceptions import ClientError

from ..config import (
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
)


# Video validation constants
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_VIDEO_DURATION_SECONDS = 60  # 60 seconds
ALLOWED_VIDEO_MIME_TYPES = [
    "video/mp4",
    "video/quicktime",  # .mov
    "video/webm",
    "video/x-msvideo",  # .avi
]


def get_r2_client():
    """Get configured boto3 client for Cloudflare R2"""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def validate_video_file(
    filename: str, size_bytes: int, mime_type: str, duration_seconds: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate video file before upload.
    
    Args:
        filename: Original filename
        size_bytes: File size in bytes
        mime_type: MIME type of the file
        duration_seconds: Video duration (optional)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size
    if size_bytes > MAX_VIDEO_SIZE_BYTES:
        return False, f"Video file size exceeds maximum of {MAX_VIDEO_SIZE_BYTES / (1024 * 1024):.0f}MB"
    
    # Check MIME type
    if mime_type not in ALLOWED_VIDEO_MIME_TYPES:
        return False, f"Video format not supported. Allowed formats: MP4, MOV, WebM"
    
    # Check duration if provided
    if duration_seconds and duration_seconds > MAX_VIDEO_DURATION_SECONDS:
        return False, f"Video duration exceeds maximum of {MAX_VIDEO_DURATION_SECONDS} seconds"
    
    # Check filename extension
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    allowed_extensions = ["mp4", "mov", "webm", "avi"]
    if ext not in allowed_extensions:
        return False, f"File extension not allowed. Use: {', '.join(allowed_extensions)}"
    
    return True, None


def generate_video_r2_key(user_id: int, client_id: int, filename: str) -> str:
    """
    Generate a unique R2 key for video storage.
    
    Format: custom-quotes/{user_id}/{client_id}/{timestamp}_{hash}_{filename}
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_hash = hashlib.md5(f"{user_id}{client_id}{timestamp}{filename}".encode()).hexdigest()[:8]
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")[:100]
    
    return f"custom-quotes/{user_id}/{client_id}/{timestamp}_{file_hash}_{safe_filename}"


def upload_video_to_r2(
    file_content: bytes,
    r2_key: str,
    mime_type: str,
    metadata: Optional[dict] = None
) -> bool:
    """
    Upload video file to R2 private bucket.
    
    Args:
        file_content: Video file bytes
        r2_key: R2 storage key
        mime_type: MIME type
        metadata: Optional metadata dict
    
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client = get_r2_client()
        
        extra_args = {
            "ContentType": mime_type,
            "ACL": "private",  # Ensure private access
        }
        
        if metadata:
            extra_args["Metadata"] = metadata
        
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key,
            Body=file_content,
            **extra_args
        )
        
        return True
    except ClientError as e:
        print(f"Error uploading video to R2: {e}")
        return False


def generate_presigned_video_url(r2_key: str, expiration_minutes: int = 15) -> Optional[str]:
    """
    Generate a presigned URL for private video access.
    
    Args:
        r2_key: R2 storage key
        expiration_minutes: URL expiration time in minutes (default 15)
    
    Returns:
        Presigned URL or None if error
    """
    try:
        s3_client = get_r2_client()
        
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": R2_BUCKET_NAME,
                "Key": r2_key,
            },
            ExpiresIn=expiration_minutes * 60,
        )
        
        return url
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None


def delete_video_from_r2(r2_key: str) -> bool:
    """
    Delete video file from R2.
    
    Args:
        r2_key: R2 storage key
    
    Returns:
        True if successful, False otherwise
    """
    try:
        s3_client = get_r2_client()
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        return True
    except ClientError as e:
        print(f"Error deleting video from R2: {e}")
        return False


def get_video_metadata(r2_key: str) -> Optional[dict]:
    """
    Get video file metadata from R2.
    
    Args:
        r2_key: R2 storage key
    
    Returns:
        Metadata dict or None if error
    """
    try:
        s3_client = get_r2_client()
        response = s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        
        return {
            "size": response.get("ContentLength"),
            "mime_type": response.get("ContentType"),
            "last_modified": response.get("LastModified"),
            "metadata": response.get("Metadata", {}),
        }
    except ClientError as e:
        print(f"Error getting video metadata: {e}")
        return None
