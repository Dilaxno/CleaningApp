import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
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
    onboardingComplete: Optional[bool] = None
    # Pricing
    pricingModel: Optional[str] = None
    meetingsRequired: Optional[bool] = None
    workingDays: Optional[List[str]] = None
    workingHours: Optional[Dict[str, str]] = None
    breakTimes: Optional[List[str]] = None
    daySchedules: Optional[Dict] = None  # Per-day working hours
    offWorkPeriods: Optional[List[Dict]] = None  # Off-work periods (vacations, holidays)
    customAddons: Optional[List[Dict]] = None  # Custom add-on services
    suppliesProvided: Optional[str] = None  # "provider" or "client"
    availableSupplies: Optional[List[str]] = None  # List of supply IDs
    ratePerSqft: Optional[str] = None
    ratePerRoom: Optional[str] = None
    hourlyRate: Optional[str] = None
    flatRate: Optional[str] = None
    minimumCharge: Optional[str] = None
    cleaningTimePerSqft: Optional[str] = None
    cleanersSmallJob: Optional[str] = None
    cleanersLargeJob: Optional[str] = None
    bufferTime: Optional[str] = None
    premiumEveningWeekend: Optional[str] = None
    premiumDeepClean: Optional[str] = None
    discountWeekly: Optional[str] = None
    discountMonthly: Optional[str] = None
    discountLongTerm: Optional[str] = None
    addonWindows: Optional[str] = None
    addonCarpets: Optional[str] = None
    paymentDueDays: Optional[str] = None
    lateFeePercent: Optional[str] = None
    standardInclusions: Optional[List[str]] = None
    standardExclusions: Optional[List[str]] = None
    customInclusions: Optional[List[str]] = None
    customExclusions: Optional[List[str]] = None
    preferredUnits: Optional[str] = None


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
        "meetingsRequired": config.meetings_required,
        "workingDays": config.working_days,
        "workingHours": config.working_hours,
        "breakTimes": config.break_times,
        "daySchedules": config.day_schedules,
        "offWorkPeriods": config.off_work_periods,
        "customAddons": config.custom_addons,
        "suppliesProvided": config.supplies_provided,
        "availableSupplies": config.available_supplies,
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
        "customInclusions": config.custom_inclusions,
        "customExclusions": config.custom_exclusions,
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
            # Only update fields that are explicitly provided (not None)
            if data.businessName is not None:
                existing.business_name = data.businessName
            if data.logoUrl is not None:
                existing.logo_url = data.logoUrl
            if data.signatureUrl is not None:
                existing.signature_url = data.signatureUrl
            if data.onboardingComplete is not None:
                logger.info(f"📝 Setting onboarding_complete to: {data.onboardingComplete}")
                existing.onboarding_complete = data.onboardingComplete
            if data.pricingModel is not None:
                existing.pricing_model = data.pricingModel
            if data.meetingsRequired is not None:
                logger.info(f"📝 Setting meetings_required to: {data.meetingsRequired}")
                existing.meetings_required = data.meetingsRequired
            if data.workingDays is not None:
                existing.working_days = data.workingDays
            if data.workingHours is not None:
                existing.working_hours = data.workingHours
            if data.breakTimes is not None:
                existing.break_times = data.breakTimes
            if data.daySchedules is not None:
                existing.day_schedules = data.daySchedules
            if data.offWorkPeriods is not None:
                existing.off_work_periods = data.offWorkPeriods
            if data.customAddons is not None:
                existing.custom_addons = data.customAddons
            if data.suppliesProvided is not None:
                existing.supplies_provided = data.suppliesProvided
            if data.availableSupplies is not None:
                existing.available_supplies = data.availableSupplies
            if data.ratePerSqft is not None:
                existing.rate_per_sqft = to_float(data.ratePerSqft)
            if data.ratePerRoom is not None:
                existing.rate_per_room = to_float(data.ratePerRoom)
            if data.hourlyRate is not None:
                existing.hourly_rate = to_float(data.hourlyRate)
            if data.flatRate is not None:
                existing.flat_rate = to_float(data.flatRate)
            if data.minimumCharge is not None:
                existing.minimum_charge = to_float(data.minimumCharge)
            if data.cleaningTimePerSqft is not None:
                existing.cleaning_time_per_sqft = to_int(data.cleaningTimePerSqft)
            if data.cleanersSmallJob is not None:
                existing.cleaners_small_job = to_int(data.cleanersSmallJob) or 1
            if data.cleanersLargeJob is not None:
                existing.cleaners_large_job = to_int(data.cleanersLargeJob) or 2
            if data.bufferTime is not None:
                existing.buffer_time = to_int(data.bufferTime) or 30
            if data.premiumEveningWeekend is not None:
                existing.premium_evening_weekend = to_float(data.premiumEveningWeekend)
            if data.premiumDeepClean is not None:
                existing.premium_deep_clean = to_float(data.premiumDeepClean)
            if data.discountWeekly is not None:
                existing.discount_weekly = to_float(data.discountWeekly)
            if data.discountMonthly is not None:
                existing.discount_monthly = to_float(data.discountMonthly)
            if data.discountLongTerm is not None:
                existing.discount_long_term = to_float(data.discountLongTerm)
            if data.addonWindows is not None:
                existing.addon_windows = to_float(data.addonWindows)
            if data.addonCarpets is not None:
                existing.addon_carpets = to_float(data.addonCarpets)
            if data.paymentDueDays is not None:
                existing.payment_due_days = to_int(data.paymentDueDays) or 15
            if data.lateFeePercent is not None:
                existing.late_fee_percent = to_float(data.lateFeePercent) or 1.5
            if data.standardInclusions is not None:
                existing.standard_inclusions = data.standardInclusions
            if data.standardExclusions is not None:
                existing.standard_exclusions = data.standardExclusions
            if data.customInclusions is not None:
                existing.custom_inclusions = data.customInclusions
            if data.customExclusions is not None:
                existing.custom_exclusions = data.customExclusions
            if data.preferredUnits is not None:
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
                meetings_required=data.meetingsRequired,
                working_days=data.workingDays,
                working_hours=data.workingHours,
                break_times=data.breakTimes,
                day_schedules=data.daySchedules,
                off_work_periods=data.offWorkPeriods,
                custom_addons=data.customAddons,
                supplies_provided=data.suppliesProvided,
                available_supplies=data.availableSupplies,
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
                custom_inclusions=data.customInclusions,
                custom_exclusions=data.customExclusions,
                preferred_units=data.preferredUnits,
            )
            db.add(config)
            db.commit()

        user.onboarding_completed = data.onboardingComplete if data.onboardingComplete is not None else user.onboarding_completed
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
    
    # Validate firebase_uid format to prevent injection
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid user identifier")
    
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
        "customInclusions": config.custom_inclusions,
        "customExclusions": config.custom_exclusions,
        "preferredUnits": config.preferred_units,
    }


@router.get("/public/branding/{firebase_uid}")
def get_public_branding(firebase_uid: str, db: Session = Depends(get_db)):
    """
    Public endpoint to get business branding (logo, name) for client-facing forms.
    No authentication required - accessed via shareable form links.
    """
    logger.info(f"📥 Getting public branding for firebase_uid: {firebase_uid}")
    
    # Validate firebase_uid format to prevent injection
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid business identifier")
    
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


@router.get("/public/addons/{firebase_uid}")
def get_public_addons(firebase_uid: str, db: Session = Depends(get_db)):
    """
    Public endpoint to get business addon services for client-facing forms.
    No authentication required - accessed via shareable form links.
    """
    logger.info(f"📥 Getting public addons for firebase_uid: {firebase_uid}")
    
    # Validate firebase_uid format to prevent injection
    if not firebase_uid or len(firebase_uid) > 128 or not firebase_uid.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid business identifier")
    
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.error(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    
    # Return empty addons if no config exists
    if not config:
        logger.info(f"⚠️ No business config found, returning empty addons")
        return {
            "customAddons": [],
            "addonWindows": None,
            "addonCarpets": None,
        }

    logger.info(f"✅ Returning public addons for user_id: {user.id}")
    return {
        "customAddons": config.custom_addons or [],
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,
    }
