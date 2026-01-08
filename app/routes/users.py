import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models import User
from ..auth import get_current_user
from .upload import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def validate_firebase_uid(firebase_uid: str) -> bool:
    """Validate firebase_uid format to prevent injection"""
    if not firebase_uid or len(firebase_uid) > 128:
        return False
    return firebase_uid.replace("-", "").replace("_", "").isalnum()


def verify_user_access(firebase_uid: str, current_user: User) -> None:
    """Verify the authenticated user has access to the requested resource"""
    if current_user.firebase_uid != firebase_uid:
        logger.warning(
            f"🚫 Access denied: User {current_user.firebase_uid} tried to access {firebase_uid}"
        )
        raise HTTPException(
            status_code=403, detail="You can only access your own user data"
        )


class UserCreate(BaseModel):
    firebaseUid: str
    email: str
    fullName: Optional[str] = None
    accountType: Optional[str] = None
    hearAbout: Optional[str] = None


class UserUpdate(BaseModel):
    fullName: Optional[str] = None
    email: Optional[str] = None
    profilePictureUrl: Optional[str] = None
    accountType: Optional[str] = None
    hearAbout: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    firebase_uid: str
    email: str
    email_verified: bool = False
    full_name: Optional[str]
    profile_picture_url: Optional[str]
    profile_picture_presigned: Optional[str] = None
    account_type: Optional[str]
    plan: Optional[str] = None
    onboarding_completed: bool

    class Config:
        from_attributes = True


@router.post("", response_model=UserResponse)
def create_or_update_user(data: UserCreate, db: Session = Depends(get_db)):
    """Create or update a user from Firebase"""
    logger.info(f"📥 Creating/updating user: {data.firebaseUid}")
    logger.info(f"📋 Data received: accountType={data.accountType}, hearAbout={data.hearAbout}")

    try:
        user = db.query(User).filter(User.firebase_uid == data.firebaseUid).first()

        if user:
            logger.info(f"📝 Updating existing user: {user.id}")
            user.email = data.email
            if data.fullName:
                user.full_name = data.fullName
            # Only update account_type and hear_about if explicitly provided (not None/empty)
            if data.accountType:
                user.account_type = data.accountType
            if data.hearAbout:
                user.hear_about = data.hearAbout
        else:
            logger.info(f"🆕 Creating new user for firebase_uid: {data.firebaseUid}")
            user = User(
                firebase_uid=data.firebaseUid,
                email=data.email,
                full_name=data.fullName,
                account_type=data.accountType,
                hear_about=data.hearAbout,
                plan=None,  # Users must select a paid plan after onboarding
            )
            db.add(user)

        db.commit()
        db.refresh(user)
        logger.info(f"✅ User saved: id={user.id}, account_type={user.account_type}, hear_about={user.hear_about}")
        
        # Generate presigned URL for profile picture if exists
        response = UserResponse.model_validate(user)
        if user.profile_picture_url:
            try:
                response.profile_picture_presigned = generate_presigned_url(user.profile_picture_url)
            except Exception:
                pass
        return response

    except Exception as e:
        logger.error(f"❌ Error saving user: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{firebase_uid}/plan-usage")
def get_plan_usage(
    firebase_uid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's plan limits and current usage (authenticated)"""
    from ..plan_limits import get_usage_stats

    # Validate firebase_uid format
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    # Verify the authenticated user is accessing their own data
    verify_user_access(firebase_uid, current_user)

    return get_usage_stats(current_user, db)


@router.get("/{firebase_uid}")
def get_user(
    firebase_uid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user by Firebase UID (authenticated - users can only access their own data)"""
    # Validate firebase_uid format
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    # Verify the authenticated user is accessing their own data
    verify_user_access(firebase_uid, current_user)

    # Generate presigned URL for profile picture if exists
    profile_picture_presigned = None
    if current_user.profile_picture_url:
        try:
            profile_picture_presigned = generate_presigned_url(
                current_user.profile_picture_url
            )
        except Exception as e:
            logger.warning(
                f"⚠️ Failed to generate presigned URL for profile picture: {e}"
            )

    return {
        "id": current_user.id,
        "firebase_uid": current_user.firebase_uid,
        "email": current_user.email,
        "email_verified": current_user.email_verified,
        "full_name": current_user.full_name,
        "profile_picture_key": current_user.profile_picture_url,
        "profile_picture_url": profile_picture_presigned,
        "account_type": current_user.account_type,
        "plan": current_user.plan,
        "hear_about": current_user.hear_about,
        "onboarding_completed": current_user.onboarding_completed,
    }


@router.put("/{firebase_uid}")
def update_user(
    firebase_uid: str,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user settings (authenticated - users can only update their own data)"""
    logger.info(f"📥 Updating user settings: {firebase_uid}")

    # Validate firebase_uid format
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    # Verify the authenticated user is updating their own data
    verify_user_access(firebase_uid, current_user)

    try:
        if data.fullName is not None:
            current_user.full_name = data.fullName
        if data.email is not None:
            current_user.email = data.email
        if data.profilePictureUrl is not None:
            current_user.profile_picture_url = data.profilePictureUrl
        if data.accountType is not None:
            current_user.account_type = data.accountType
        if data.hearAbout is not None:
            current_user.hear_about = data.hearAbout

        db.commit()
        db.refresh(current_user)

        # Generate presigned URL for profile picture if exists
        profile_picture_presigned = None
        if current_user.profile_picture_url:
            try:
                profile_picture_presigned = generate_presigned_url(
                    current_user.profile_picture_url
                )
            except Exception:
                pass

        logger.info(f"✅ User updated: id={current_user.id}")
        return {
            "id": current_user.id,
            "firebase_uid": current_user.firebase_uid,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "profile_picture_key": current_user.profile_picture_url,
            "profile_picture_url": profile_picture_presigned,
            "account_type": current_user.account_type,
            "plan": current_user.plan,
            "hear_about": current_user.hear_about,
            "onboarding_completed": current_user.onboarding_completed,
        }

    except Exception as e:
        logger.error(f"❌ Error updating user: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{firebase_uid}")
def patch_user(
    firebase_uid: str,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update user settings (authenticated - same as PUT)"""
    return update_user(firebase_uid, data, current_user, db)
