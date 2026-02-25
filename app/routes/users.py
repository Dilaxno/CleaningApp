import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..shared.validators import validate_corporate_email
from .upload import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def validate_firebase_uid(firebase_uid: str) -> bool:
    """Validate firebase_uid format using strict Firebase UID pattern"""
    if not firebase_uid:
        return False

    # Firebase UIDs are exactly 28 characters, alphanumeric with possible hyphens and underscores
    # They follow a specific pattern: base64url-encoded 128-bit identifier
    import re

    firebase_uid_pattern = r"^[a-zA-Z0-9_-]{28}$"

    if not re.match(firebase_uid_pattern, firebase_uid):
        return False

    # Additional length check for safety
    if len(firebase_uid) != 28:
        return False

    return True


def verify_user_access(firebase_uid: str, current_user: User) -> None:
    """Verify the authenticated user has access to the requested resource"""
    if current_user.firebase_uid != firebase_uid:
        logger.warning(
            f"🚫 Access denied: User {current_user.firebase_uid} tried to access {firebase_uid}"
        )
        raise HTTPException(status_code=403, detail="You can only access your own user data")


class UserCreate(BaseModel):
    firebaseUid: str
    email: str
    fullName: Optional[str] = None
    accountType: Optional[str] = None
    hearAbout: Optional[str] = None
    profilePictureUrl: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, v: str) -> str:
        """Validate that email is a corporate email"""
        return validate_corporate_email(v)


class UserUpdate(BaseModel):
    fullName: Optional[str] = None
    email: Optional[str] = None
    profilePictureUrl: Optional[str] = None
    accountType: Optional[str] = None
    hearAbout: Optional[str] = None
    plan: Optional[str] = None
    default_brand_color: Optional[str] = None
    onboarding_step: Optional[int] = None
    onboarding_completed: Optional[bool] = None  # CRITICAL: Allow updating onboarding completion
    oauth_states: Optional[dict] = None


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
    onboarding_step: int = 1
    oauth_states: Optional[dict] = None

    class Config:
        from_attributes = True


@router.post("", response_model=UserResponse)
def create_or_update_user(data: UserCreate, db: Session = Depends(get_db)):
    """Create or update a user from Firebase"""
    logger.info(f"📥 Creating/updating user: {data.firebaseUid}")
    logger.info(f"📋 Data received: accountType={data.accountType}, hearAbout={data.hearAbout}")

    # Validate profile picture URL - reject data URIs (too long for database)
    profile_picture_url = None
    if data.profilePictureUrl:
        if data.profilePictureUrl.startswith("data:"):
            logger.warning(
                f"⚠️ Ignoring data URI profile picture (too long for storage): {data.profilePictureUrl[:50]}..."
            )
        elif data.profilePictureUrl.startswith("http"):
            # Accept HTTP/HTTPS URLs (Google profile pictures, etc.)
            profile_picture_url = data.profilePictureUrl
        else:
            # Accept R2 storage keys
            profile_picture_url = data.profilePictureUrl

    try:
        user = db.query(User).filter(User.firebase_uid == data.firebaseUid).first()

        if user:
            user.email = data.email
            if data.fullName:
                user.full_name = data.fullName
            # Only update account_type and hear_about if explicitly provided (not None/empty)
            if data.accountType:
                user.account_type = data.accountType
            if data.hearAbout:
                user.hear_about = data.hearAbout
            # Set profile picture from Google if provided and user doesn't have one
            if profile_picture_url and not user.profile_picture_url:
                user.profile_picture_url = profile_picture_url
        else:
            logger.info(f"🆕 Creating new user for firebase_uid: {data.firebaseUid}")
            # Only set profile picture if explicitly provided
            user = User(
                firebase_uid=data.firebaseUid,
                email=data.email,
                full_name=data.fullName,
                account_type=data.accountType,
                hear_about=data.hearAbout,
                profile_picture_url=profile_picture_url,  # Only set if provided, otherwise None
                plan=None,  # Users must select a paid plan after onboarding
            )
            db.add(user)

        db.commit()
        db.refresh(user)
        # Generate presigned URL for profile picture if exists
        response = UserResponse.model_validate(user)
        if user.profile_picture_url:
            try:
                response.profile_picture_presigned = generate_presigned_url(
                    user.profile_picture_url
                )
            except Exception as e:
                logger.warning(f"Failed to generate presigned URL for profile picture: {e}")
        return response

    except Exception as e:
        logger.error(f"❌ Error saving user: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


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
            profile_picture_presigned = generate_presigned_url(current_user.profile_picture_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for profile picture: {e}")

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
        "billing_cycle": current_user.billing_cycle,  # Include billing cycle
        "hear_about": current_user.hear_about,
        "onboarding_completed": current_user.onboarding_completed,
        "onboarding_step": current_user.onboarding_step,
        "oauth_states": current_user.oauth_states or {},
        "default_brand_color": current_user.default_brand_color,
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
            # Validate profile picture URL - reject data URIs (too long for database)
            if data.profilePictureUrl.startswith("data:"):
                logger.warning(
                    f"⚠️ Ignoring data URI profile picture (too long for storage): {data.profilePictureUrl[:50]}..."
                )
            elif data.profilePictureUrl.startswith("http") or not data.profilePictureUrl.startswith(
                "data:"
            ):
                # Accept HTTP/HTTPS URLs or R2 storage keys
                current_user.profile_picture_url = data.profilePictureUrl
        if data.accountType is not None:
            current_user.account_type = data.accountType
        if data.hearAbout is not None:
            current_user.hear_about = data.hearAbout
        if data.plan is not None:
            current_user.plan = data.plan
            logger.info(f"📋 User plan updated to: {data.plan}")
        if data.default_brand_color is not None:
            current_user.default_brand_color = data.default_brand_color
            logger.info(f"🎨 User default brand color updated to: {data.default_brand_color}")
        if data.onboarding_step is not None:
            current_user.onboarding_step = data.onboarding_step
            logger.info(f"📍 User onboarding step updated to: {data.onboarding_step}")
        if data.onboarding_completed is not None:
            current_user.onboarding_completed = data.onboarding_completed
            logger.info(f"✅ User onboarding_completed updated to: {data.onboarding_completed}")
        if data.oauth_states is not None:
            current_user.oauth_states = data.oauth_states
            logger.info(f"🔗 User OAuth states updated")

        db.commit()
        db.refresh(current_user)

        # Generate presigned URL for profile picture if exists
        profile_picture_presigned = None
        if current_user.profile_picture_url:
            try:
                profile_picture_presigned = generate_presigned_url(current_user.profile_picture_url)
            except Exception as e:
                logger.warning(f"Failed to generate presigned URL for profile picture: {e}")
        return {
            "id": current_user.id,
            "firebase_uid": current_user.firebase_uid,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "profile_picture_key": current_user.profile_picture_url,
            "profile_picture_url": profile_picture_presigned,
            "account_type": current_user.account_type,
            "plan": current_user.plan,
            "billing_cycle": current_user.billing_cycle,  # Include billing cycle
            "hear_about": current_user.hear_about,
            "onboarding_completed": current_user.onboarding_completed,
            "onboarding_step": current_user.onboarding_step,
            "oauth_states": current_user.oauth_states or {},
            "default_brand_color": current_user.default_brand_color,
        }

    except Exception as e:
        logger.error(f"❌ Error updating user: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{firebase_uid}")
def patch_user(
    firebase_uid: str,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update user settings (authenticated - same as PUT)"""
    return update_user(firebase_uid, data, current_user, db)


@router.post("/{firebase_uid}/skip-sms-onboarding")
def skip_sms_onboarding(
    firebase_uid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark that user skipped SMS setup during onboarding"""
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    verify_user_access(firebase_uid, current_user)

    try:
        current_user.sms_onboarding_skipped = True
        db.commit()
        logger.info(f"📱 User {current_user.id} skipped SMS onboarding")
        return {"success": True, "message": "SMS onboarding skipped"}
    except Exception as e:
        logger.error(f"❌ Error marking SMS onboarding as skipped: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


class CompleteOnboardingRequest(BaseModel):
    firebaseUid: str
    businessName: str
    ownerEmail: str
    ownerPhone: str
    serviceRegion: str
    serviceStates: list[str]
    serviceCities: list[str]
    serviceZipCodes: str
    pricingModel: str
    minimumJobPrice: float
    recurringDiscounts: dict
    acceptedFrequencies: list[str]
    paymentDueDays: int
    lateFeePercent: float
    cancellationWindow: int
    standardInclusions: list[str]
    standardExclusions: list[str]
    daySchedules: dict
    formEmbeddingEnabled: bool
    paymentHandling: str
    paymentMethod: str
    smsEnabled: bool
    onboardingComplete: bool


@router.post("/{firebase_uid}/complete-onboarding")
def complete_onboarding(
    firebase_uid: str,
    data: CompleteOnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete user onboarding and create business configuration"""
    from ..models import BusinessConfig

    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid user identifier")

    verify_user_access(firebase_uid, current_user)

    try:
        # Update user onboarding status
        current_user.onboarding_completed = data.onboardingComplete
        logger.info(f"✅ User {current_user.id} completed onboarding")

        # Create or update business config
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
        )

        # Prepare service areas data
        service_areas_data = {
            "states": data.serviceStates,
            "cities": data.serviceCities,
            "zipCodes": data.serviceZipCodes,
            "region": data.serviceRegion,  # Keep legacy field for backward compatibility
        }

        if business_config:
            # Update existing config
            business_config.business_name = data.businessName
            business_config.business_phone = data.ownerPhone
            business_config.service_areas = [service_areas_data]
            business_config.pricing_model = data.pricingModel
            business_config.minimum_charge = str(data.minimumJobPrice)
            business_config.discount_weekly = str(data.recurringDiscounts.get("weekly", 0))
            business_config.discount_biweekly = str(data.recurringDiscounts.get("biweekly", 0))
            business_config.discount_monthly = str(data.recurringDiscounts.get("monthly", 0))
            business_config.accepted_frequencies = data.acceptedFrequencies
            business_config.payment_due_days = str(data.paymentDueDays)
            business_config.late_fee_percent = str(data.lateFeePercent)
            business_config.cancellation_window = str(data.cancellationWindow)
            business_config.standard_inclusions = data.standardInclusions
            business_config.standard_exclusions = data.standardExclusions
            business_config.day_schedules = data.daySchedules
            business_config.form_embedding_enabled = data.formEmbeddingEnabled
            business_config.payment_handling = data.paymentHandling
            business_config.payment_method = data.paymentMethod
            logger.info(f"📝 Updated business config for user {current_user.id}")
        else:
            # Create new config
            business_config = BusinessConfig(
                user_id=current_user.id,
                business_name=data.businessName,
                business_phone=data.ownerPhone,
                service_areas=[service_areas_data],
                pricing_model=data.pricingModel,
                minimum_charge=str(data.minimumJobPrice),
                discount_weekly=str(data.recurringDiscounts.get("weekly", 0)),
                discount_biweekly=str(data.recurringDiscounts.get("biweekly", 0)),
                discount_monthly=str(data.recurringDiscounts.get("monthly", 0)),
                accepted_frequencies=data.acceptedFrequencies,
                payment_due_days=str(data.paymentDueDays),
                late_fee_percent=str(data.lateFeePercent),
                cancellation_window=str(data.cancellationWindow),
                standard_inclusions=data.standardInclusions,
                standard_exclusions=data.standardExclusions,
                day_schedules=data.daySchedules,
                form_embedding_enabled=data.formEmbeddingEnabled,
                payment_handling=data.paymentHandling,
                payment_method=data.paymentMethod,
            )
            db.add(business_config)
            logger.info(f"🆕 Created business config for user {current_user.id}")

        db.commit()
        db.refresh(current_user)

        return {
            "success": True,
            "message": "Onboarding completed successfully",
            "onboarding_completed": current_user.onboarding_completed,
        }

    except Exception as e:
        logger.error(f"❌ Error completing onboarding: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


# Payout Information Models
class PayoutInfoUpdate(BaseModel):
    country: str  # ISO country code
    currency: str  # Currency code
    accountHolderName: str
    bankName: Optional[str] = None
    accountNumber: Optional[str] = None
    routingNumber: Optional[str] = None  # US routing / UK sort code
    iban: Optional[str] = None  # IBAN for Europe
    swiftBic: Optional[str] = None  # SWIFT/BIC code
    bankAddress: Optional[str] = None


class PayoutInfoResponse(BaseModel):
    country: Optional[str] = None
    currency: Optional[str] = None
    accountHolderName: Optional[str] = None
    bankName: Optional[str] = None
    accountNumber: Optional[str] = None  # Masked for security
    routingNumber: Optional[str] = None  # Masked for security
    iban: Optional[str] = None  # Masked for security
    swiftBic: Optional[str] = None
    bankAddress: Optional[str] = None
    isConfigured: bool = False


def mask_sensitive(value: Optional[str], visible_chars: int = 2) -> Optional[str]:
    """Mask sensitive data, showing only first 2 and last 2 characters for security"""
    if not value or len(value) <= 4:
        return "****" if value else None  # Always mask short values
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


@router.get("/{firebase_uid}/payout-info", response_model=PayoutInfoResponse)
def get_payout_info(
    firebase_uid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's payout information (masked for security)"""
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid firebase_uid format")

    verify_user_access(firebase_uid, current_user)

    is_configured = bool(
        current_user.payout_country
        and current_user.payout_account_holder_name
        and (current_user.payout_account_number or current_user.payout_iban)
    )

    return PayoutInfoResponse(
        country=current_user.payout_country,
        currency=current_user.payout_currency,
        accountHolderName=current_user.payout_account_holder_name,
        bankName=current_user.payout_bank_name,
        accountNumber=mask_sensitive(current_user.payout_account_number),
        routingNumber=mask_sensitive(current_user.payout_routing_number),
        iban=mask_sensitive(current_user.payout_iban),
        swiftBic=current_user.payout_swift_bic,
        bankAddress=current_user.payout_bank_address,
        isConfigured=is_configured,
    )


@router.put("/{firebase_uid}/payout-info")
def update_payout_info(
    firebase_uid: str,
    data: PayoutInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user's payout information"""
    if not validate_firebase_uid(firebase_uid):
        raise HTTPException(status_code=400, detail="Invalid firebase_uid format")

    verify_user_access(firebase_uid, current_user)

    logger.info(f"📥 Updating payout info for user: {current_user.id}")

    try:
        current_user.payout_country = data.country
        current_user.payout_currency = data.currency
        current_user.payout_account_holder_name = data.accountHolderName
        current_user.payout_bank_name = data.bankName
        current_user.payout_account_number = data.accountNumber
        current_user.payout_routing_number = data.routingNumber
        current_user.payout_iban = data.iban
        current_user.payout_swift_bic = data.swiftBic
        current_user.payout_bank_address = data.bankAddress

        db.commit()
        db.refresh(current_user)
        return {"success": True, "message": "Payout information saved successfully"}
    except Exception as e:
        logger.error(f"❌ Error updating payout info: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
