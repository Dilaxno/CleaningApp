import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models import User, BusinessConfig
from ..auth import get_current_user
from .upload import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/business-config", tags=["Business Configuration"])


class BusinessConfigCreate(BaseModel):
    firebaseUid: str
    # Branding
    businessName: Optional[str] = None
    logoUrl: Optional[str] = None
    signatureUrl: Optional[str] = None
    onboardingComplete: Optional[bool] = False
    # Pricing
    pricingModel: str
    ratePerSqft: Optional[str] = None
    ratePerRoom: Optional[str] = None
    hourlyRate: Optional[str] = None
    flatRate: Optional[str] = None
    minimumCharge: Optional[str] = None
    cleaningTimePerSqft: Optional[str] = None
    cleanersSmallJob: Optional[str] = "1"
    cleanersLargeJob: Optional[str] = "2"
    bufferTime: Optional[str] = "30"
    premiumEveningWeekend: Optional[str] = None
    premiumDeepClean: Optional[str] = None
    discountWeekly: Optional[str] = None
    discountMonthly: Optional[str] = None
    discountLongTerm: Optional[str] = None
    addonWindows: Optional[str] = None
    addonCarpets: Optional[str] = None
    paymentDueDays: Optional[str] = "15"
    lateFeePercent: Optional[str] = "1.5"
    standardInclusions: Optional[List[str]] = []
    standardExclusions: Optional[List[str]] = []
    preferredUnits: Optional[str] = "sqft"


def to_float(val: Optional[str]) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def to_int(val: Optional[str]) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


@router.get("")
def get_current_user_business_config(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get business config for the currently authenticated user"""
    logger.info(f"📥 Getting business config for current user: {current_user.id}")
    
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == current_user.id).first()
    if not config:
        logger.warning(f"⚠️ Business config not found for user_id: {current_user.id}")
        raise HTTPException(status_code=404, detail="Business config not found")

    # Generate presigned URLs for logo and signature if they exist
    logo_presigned_url = None
    signature_presigned_url = None
    
    if config.logo_url:
        try:
            logo_presigned_url = generate_presigned_url(config.logo_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for logo: {e}")
    
    if config.signature_url:
        try:
            signature_presigned_url = generate_presigned_url(config.signature_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for signature: {e}")

    logger.info(f"✅ Found business config for user_id: {current_user.id}")
    return {
        "businessName": config.business_name,
        "logoKey": config.logo_url,
        "logoUrl": logo_presigned_url,
        "signatureKey": config.signature_url,
        "signatureUrl": signature_presigned_url,
        "onboardingComplete": config.onboarding_complete,
        "pricingModel": config.pricing_model,
        "ratePerSqft": config.rate_per_sqft,
        "ratePerRoom": config.rate_per_room,
        "hourlyRate": config.hourly_rate,
        "flatRate": config.flat_rate,
        "minimumCharge": config.minimum_charge,
        "cleaningTimePerSqft": config.cleaning_time_per_sqft,
        "cleanersSmallJob": config.cleaners_small_job,
        "cleanersLargeJob": config.cleaners_large_job,
        "bufferTime": config.buffer_time,
        "premiumEveningWeekend": config.premium_evening_weekend,
        "premiumDeepClean": config.premium_deep_clean,
        "discountWeekly": config.discount_weekly,
        "discountMonthly": config.discount_monthly,
        "discountLongTerm": config.discount_long_term,
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,
        "paymentDueDays": config.payment_due_days,
        "lateFeePercent": config.late_fee_percent,
        "standardInclusions": config.standard_inclusions,
        "standardExclusions": config.standard_exclusions,
        "preferredUnits": config.preferred_units,
    }


@router.post("")
def create_business_config(data: BusinessConfigCreate, db: Session = Depends(get_db)):
    logger.info(f"📥 Creating business config for firebase_uid: {data.firebaseUid}")
    logger.info(f"📋 Data received: pricingModel={data.pricingModel}")
    
    try:
        user = db.query(User).filter(User.firebase_uid == data.firebaseUid).first()
        if not user:
            logger.error(f"❌ User not found for firebase_uid: {data.firebaseUid}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"✅ Found user: id={user.id}, email={user.email}")

        existing = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if existing:
            logger.info(f"📝 Updating existing config for user_id: {user.id}")
            existing.business_name = data.businessName
            existing.logo_url = data.logoUrl
            existing.signature_url = data.signatureUrl
            existing.onboarding_complete = data.onboardingComplete
            existing.pricing_model = data.pricingModel
            existing.rate_per_sqft = to_float(data.ratePerSqft)
            existing.rate_per_room = to_float(data.ratePerRoom)
            existing.hourly_rate = to_float(data.hourlyRate)
            existing.flat_rate = to_float(data.flatRate)
            existing.minimum_charge = to_float(data.minimumCharge)
            existing.cleaning_time_per_sqft = to_int(data.cleaningTimePerSqft)
            existing.cleaners_small_job = to_int(data.cleanersSmallJob) or 1
            existing.cleaners_large_job = to_int(data.cleanersLargeJob) or 2
            existing.buffer_time = to_int(data.bufferTime) or 30
            existing.premium_evening_weekend = to_float(data.premiumEveningWeekend)
            existing.premium_deep_clean = to_float(data.premiumDeepClean)
            existing.discount_weekly = to_float(data.discountWeekly)
            existing.discount_monthly = to_float(data.discountMonthly)
            existing.discount_long_term = to_float(data.discountLongTerm)
            existing.addon_windows = to_float(data.addonWindows)
            existing.addon_carpets = to_float(data.addonCarpets)
            existing.payment_due_days = to_int(data.paymentDueDays) or 15
            existing.late_fee_percent = to_float(data.lateFeePercent) or 1.5
            existing.standard_inclusions = data.standardInclusions
            existing.standard_exclusions = data.standardExclusions
            existing.preferred_units = data.preferredUnits
            db.commit()
            config = existing
        else:
            logger.info(f"🆕 Creating new config for user_id: {user.id}")
            config = BusinessConfig(
                user_id=user.id,
                business_name=data.businessName,
                logo_url=data.logoUrl,
                signature_url=data.signatureUrl,
                onboarding_complete=data.onboardingComplete,
                pricing_model=data.pricingModel,
                rate_per_sqft=to_float(data.ratePerSqft),
                rate_per_room=to_float(data.ratePerRoom),
                hourly_rate=to_float(data.hourlyRate),
                flat_rate=to_float(data.flatRate),
                minimum_charge=to_float(data.minimumCharge),
                cleaning_time_per_sqft=to_int(data.cleaningTimePerSqft),
                cleaners_small_job=to_int(data.cleanersSmallJob) or 1,
                cleaners_large_job=to_int(data.cleanersLargeJob) or 2,
                buffer_time=to_int(data.bufferTime) or 30,
                premium_evening_weekend=to_float(data.premiumEveningWeekend),
                premium_deep_clean=to_float(data.premiumDeepClean),
                discount_weekly=to_float(data.discountWeekly),
                discount_monthly=to_float(data.discountMonthly),
                discount_long_term=to_float(data.discountLongTerm),
                addon_windows=to_float(data.addonWindows),
                addon_carpets=to_float(data.addonCarpets),
                payment_due_days=to_int(data.paymentDueDays) or 15,
                late_fee_percent=to_float(data.lateFeePercent) or 1.5,
                standard_inclusions=data.standardInclusions,
                standard_exclusions=data.standardExclusions,
                preferred_units=data.preferredUnits,
            )
            db.add(config)
            db.commit()

        user.onboarding_completed = True
        db.commit()
        
        logger.info(f"✅ Business config saved successfully, id={config.id}")
        return {"message": "Business configuration saved", "id": config.id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating business config: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{firebase_uid}")
def get_business_config(firebase_uid: str, db: Session = Depends(get_db)):
    logger.info(f"📥 Getting business config for firebase_uid: {firebase_uid}")
    
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.error(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="User not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        logger.warning(f"⚠️ Business config not found for user_id: {user.id}")
        raise HTTPException(status_code=404, detail="Business config not found")

    # Generate presigned URLs for logo and signature if they exist
    logo_presigned_url = None
    signature_presigned_url = None
    
    if config.logo_url:
        try:
            logo_presigned_url = generate_presigned_url(config.logo_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for logo: {e}")
    
    if config.signature_url:
        try:
            signature_presigned_url = generate_presigned_url(config.signature_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for signature: {e}")

    logger.info(f"✅ Found business config for user_id: {user.id}")
    return {
        "businessName": config.business_name,
        "logoKey": config.logo_url,  # The R2 key
        "logoUrl": logo_presigned_url,  # Presigned URL for display
        "signatureKey": config.signature_url,  # The R2 key
        "signatureUrl": signature_presigned_url,  # Presigned URL for display
        "pricingModel": config.pricing_model,
        "ratePerSqft": config.rate_per_sqft,
        "ratePerRoom": config.rate_per_room,
        "hourlyRate": config.hourly_rate,
        "flatRate": config.flat_rate,
        "minimumCharge": config.minimum_charge,
        "cleaningTimePerSqft": config.cleaning_time_per_sqft,
        "cleanersSmallJob": config.cleaners_small_job,
        "cleanersLargeJob": config.cleaners_large_job,
        "bufferTime": config.buffer_time,
        "premiumEveningWeekend": config.premium_evening_weekend,
        "premiumDeepClean": config.premium_deep_clean,
        "discountWeekly": config.discount_weekly,
        "discountMonthly": config.discount_monthly,
        "discountLongTerm": config.discount_long_term,
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,
        "paymentDueDays": config.payment_due_days,
        "lateFeePercent": config.late_fee_percent,
        "standardInclusions": config.standard_inclusions,
        "standardExclusions": config.standard_exclusions,
        "preferredUnits": config.preferred_units,
    }


@router.get("/public/branding/{firebase_uid}")
def get_public_branding(firebase_uid: str, db: Session = Depends(get_db)):
    """
    Public endpoint to get business branding (logo, name) for client-facing forms.
    No authentication required - accessed via shareable form links.
    """
    logger.info(f"📥 Getting public branding for firebase_uid: {firebase_uid}")
    
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.error(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    
    # Return default branding if no config exists
    if not config:
        logger.info(f"⚠️ No business config found, returning default branding")
        return {
            "businessName": None,
            "logoUrl": None,
        }

    # Generate presigned URL for logo if it exists
    logo_presigned_url = None
    if config.logo_url:
        try:
            logo_presigned_url = generate_presigned_url(config.logo_url)
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate presigned URL for logo: {e}")

    logger.info(f"✅ Returning public branding for user_id: {user.id}")
    return {
        "businessName": config.business_name,
        "logoUrl": logo_presigned_url,
    }
