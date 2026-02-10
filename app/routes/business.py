import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import BusinessConfig, User
from .upload import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter()


class BusinessConfigCreate(BaseModel):
    firebaseUid: str
    # Branding
    businessName: Optional[str] = None
    logoUrl: Optional[str] = None
    signatureUrl: Optional[str] = None
    onboardingComplete: Optional[bool] = None
    formEmbeddingEnabled: Optional[bool] = None
    # White-label public form links
    customFormsDomain: Optional[str] = None  # e.g., forms.cleaningco.com
    # Service Areas
    serviceAreas: Optional[List[Dict]] = None  # Service area configuration
    # Pricing
    pricingModel: Optional[str] = None
    meetingsRequired: Optional[bool] = None
    paymentHandling: Optional[str] = None  # "manual" or "automatic"
    cancellationWindow: Optional[str] = None  # Hours notice required for cancellation
    workingDays: Optional[List[str]] = None
    workingHours: Optional[Dict[str, str]] = None
    breakTimes: Optional[List[str]] = None
    daySchedules: Optional[Dict] = None  # Per-day working hours
    offWorkPeriods: Optional[List[Dict]] = (
        None  # Off-work periods (vacations, holidays)
    )
    customAddons: Optional[List[Dict]] = None  # Custom add-on services
    suppliesProvided: Optional[str] = None  # "provider" or "client"
    availableSupplies: Optional[List[str]] = None  # List of supply IDs
    ratePerSqft: Optional[str] = None
    ratePerRoom: Optional[str] = None
    hourlyRate: Optional[str] = None
    flatRate: Optional[str] = None
    flatRateSmall: Optional[str] = None
    flatRateMedium: Optional[str] = None
    flatRateLarge: Optional[str] = None
    minimumCharge: Optional[str] = None
    # Legacy field - kept for backward compatibility
    cleaningTimePerSqft: Optional[str] = None
    # New three-category time estimation system
    timeSmallJob: Optional[str] = None
    timeMediumJob: Optional[str] = None
    timeLargeJob: Optional[str] = None
    cleanersSmallJob: Optional[str] = None
    cleanersLargeJob: Optional[str] = None
    bufferTime: Optional[str] = None
    premiumEveningWeekend: Optional[str] = None
    premiumDeepClean: Optional[str] = None
    discountWeekly: Optional[str] = None
    discountBiweekly: Optional[str] = None
    discountMonthly: Optional[str] = None
    discountLongTerm: Optional[str] = None

    # First cleaning discount (applied only to the first cleaning session)
    firstCleaningDiscountType: Optional[str] = None  # percent | fixed
    firstCleaningDiscountValue: Optional[str] = None

    addonWindows: Optional[str] = None
    addonCarpets: Optional[str] = None  # Legacy - deprecated
    addonCarpetSmall: Optional[str] = None
    addonCarpetMedium: Optional[str] = None
    addonCarpetLarge: Optional[str] = None
    paymentDueDays: Optional[str] = None
    lateFeePercent: Optional[str] = None
    standardInclusions: Optional[List[str]] = None
    standardExclusions: Optional[List[str]] = None
    customInclusions: Optional[List[str]] = None
    customExclusions: Optional[List[str]] = None
    preferredUnits: Optional[str] = None
    
    # Custom packages for "packages" pricing model
    customPackages: Optional[List[Dict]] = None
    
    # Active templates - list of template IDs that the business owner has selected to work with
    activeTemplates: Optional[List[str]] = None
    
    # Accepted frequencies and payment methods
    acceptedFrequencies: Optional[List[str]] = None  # Array of accepted cleaning frequencies
    acceptedPaymentMethods: Optional[List[str]] = None  # Array of accepted payment methods
    
    # Brand color
    brandColor: Optional[str] = None  # Hex color code for branding (e.g., #00C4B4)


def to_float(val: Optional[str]) -> Optional[float]:
    """Convert string to float, returning None for empty/invalid values or 0."""
    if val is None or val == "":
        return None
    try:
        result = float(val)
        # Treat 0 as None (no discount/premium)
        return None if result == 0 else result
    except ValueError:
        return None


def to_int(val: Optional[str]) -> Optional[int]:
    """Convert string to int, returning None for empty/invalid values."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


def is_provided(val) -> bool:
    """Check if a value was actually provided (not None and not empty string)."""
    if val is None:
        return False
    if isinstance(val, str) and val == "":
        return False
    return True


@router.get("/public/{firebase_uid}")
def get_public_business_info(
    firebase_uid: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Get public business info for embedding (no authentication required)"""
    logger.info(f"📥 Getting public business info for firebase_uid: {firebase_uid}")

    # Custom domain security validation
    if hasattr(request.state, 'is_custom_domain') and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (not hasattr(request.state, 'custom_domain_user_uid') or 
            request.state.custom_domain_user_uid != firebase_uid):
            logger.warning(
                f"🚫 Custom domain security violation in business info: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match requested user {firebase_uid}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: Custom domain does not match requested user"
            )
        logger.info(f"✅ Custom domain validation passed for business info {firebase_uid}")

    # Find user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.warning(f"⚠️ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    # Get business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        logger.warning(f"⚠️ Business config not found for user_id: {user.id}")
        raise HTTPException(status_code=404, detail="Business not found")

    # Return only public information
    return {
        "businessName": config.business_name,
        "formEmbeddingEnabled": config.form_embedding_enabled,
    }


@router.get("")
def get_current_user_business_config(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get business config for the currently authenticated user"""
    logger.info(f"📥 Getting business config for current user: {current_user.id}")

    config = (
        db.query(BusinessConfig)
        .filter(BusinessConfig.user_id == current_user.id)
        .first()
    )
    
    # CRITICAL FIX: If BusinessConfig doesn't exist, check User.onboarding_completed
    # This prevents users from losing onboarding progress when switching devices
    if not config:
        logger.info(f"📋 BusinessConfig not found for user {current_user.id}, checking User.onboarding_completed")
        
        # If user has completed onboarding (stored in User table), return minimal config
        if current_user.onboarding_completed:
            logger.info(f"✅ User {current_user.id} has completed onboarding (from User table)")
            return {
                "businessName": None,
                "logoKey": None,
                "logoUrl": None,
                "signatureKey": None,
                "signatureUrl": None,
                "onboardingComplete": True,  # Use User.onboarding_completed as fallback
                "formEmbeddingEnabled": False,
                "customFormsDomain": None,
                "pricingModel": None,
                "meetingsRequired": None,
                "paymentHandling": None,
                "cancellationWindow": None,
                "workingDays": [],
                "workingHours": {},
                "breakTimes": [],
                "daySchedules": {},
                "offWorkPeriods": [],
                "customAddons": [],
                "customPackages": [],
                "suppliesProvided": None,
                "availableSupplies": [],
                "ratePerSqft": None,
                "ratePerRoom": None,
                "hourlyRate": None,
                "flatRate": None,
                "flatRateSmall": None,
                "flatRateMedium": None,
                "flatRateLarge": None,
                "minimumCharge": None,
                "brandColor": "#00C4B4",  # Default brand color
                "firstCleaningDiscount": None,
                "firstCleaningDiscountType": None,
                "firstCleaningDiscountValue": None,
                "carpetCleaningRate": None,
                "carpetCleaningRateType": None,
                "carpetCleaningMinimum": None,
                "carpetCleaningMaxRooms": None,
                "carpetCleaningFlatRateSmall": None,
                "carpetCleaningFlatRateMedium": None,
                "carpetCleaningFlatRateLarge": None,
                "threeTimeEstimation": False,
                "quickTimeEstimate": None,
                "standardTimeEstimate": None,
                "deepTimeEstimate": None,
                "activeTemplates": [],
                "acceptedFrequencies": ["one-time", "daily", "2x-per-week", "3x-per-week", "weekly", "bi-weekly", "monthly"],
                "acceptedPaymentMethods": [],
            }
        else:
            # User hasn't completed onboarding, return 404 as before
            logger.warning(f"⚠️ Business config not found and onboarding not completed for user_id: {current_user.id}")
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

    # CRITICAL FIX: Always check both BusinessConfig.onboarding_complete AND User.onboarding_completed
    # Return true if EITHER is true (prevents losing onboarding status)
    onboarding_complete = config.onboarding_complete or current_user.onboarding_completed
    
    logger.info(f"🔄 Onboarding status check for user {current_user.id}:")
    logger.info(f"   - BusinessConfig.onboarding_complete: {config.onboarding_complete}")
    logger.info(f"   - User.onboarding_completed: {current_user.onboarding_completed}")
    logger.info(f"   - Returning onboardingComplete: {onboarding_complete}")

    return {
        "businessName": config.business_name,
        "logoKey": config.logo_url,
        "logoUrl": logo_presigned_url,
        "signatureKey": config.signature_url,
        "signatureUrl": signature_presigned_url,
        "onboardingComplete": onboarding_complete,  # Use OR logic for reliability
        "formEmbeddingEnabled": config.form_embedding_enabled,
        "customFormsDomain": config.custom_forms_domain,
        "pricingModel": config.pricing_model,
        "meetingsRequired": config.meetings_required,
        "paymentHandling": config.payment_handling,
        "cancellationWindow": config.cancellation_window,
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
        "flatRateSmall": config.flat_rate_small,
        "flatRateMedium": config.flat_rate_medium,
        "flatRateLarge": config.flat_rate_large,
        "minimumCharge": config.minimum_charge,
        "cleaningTimePerSqft": config.cleaning_time_per_sqft,
        "timeSmallJob": config.time_small_job,
        "timeMediumJob": config.time_medium_job,
        "timeLargeJob": config.time_large_job,
        "cleanersSmallJob": config.cleaners_small_job,
        "cleanersLargeJob": config.cleaners_large_job,
        "bufferTime": config.buffer_time,
        "premiumEveningWeekend": config.premium_evening_weekend,
        "premiumDeepClean": config.premium_deep_clean,
        "discountWeekly": config.discount_weekly,
        "discountBiweekly": config.discount_biweekly,
        "discountMonthly": config.discount_monthly,
        "discountLongTerm": config.discount_long_term,
        "firstCleaningDiscountType": config.first_cleaning_discount_type,
        "firstCleaningDiscountValue": config.first_cleaning_discount_value,
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,
        "paymentDueDays": config.payment_due_days,
        "lateFeePercent": config.late_fee_percent,
        "standardInclusions": config.standard_inclusions,
        "standardExclusions": config.standard_exclusions,
        "customInclusions": config.custom_inclusions,
        "customExclusions": config.custom_exclusions,
        "preferredUnits": config.preferred_units,
        "addonCarpetSmall": config.addon_carpet_small,
        "addonCarpetMedium": config.addon_carpet_medium,
        "addonCarpetLarge": config.addon_carpet_large,
        "customPackages": config.custom_packages,
        "activeTemplates": config.active_templates,
        "acceptedFrequencies": config.accepted_frequencies,
        "acceptedPaymentMethods": config.accepted_payment_methods,
        "brandColor": config.brand_color,
        "serviceAreas": config.service_areas,
    }


@router.post("")
def create_business_config(data: BusinessConfigCreate, db: Session = Depends(get_db)):
    logger.info(f"📥 Creating business config for firebase_uid: {data.firebaseUid}")
    logger.info(
        f"📋 Data received: pricingModel={data.pricingModel}, logoUrl={data.logoUrl}"
    )
    logger.info(
        f"📋 Pricing data: ratePerSqft={data.ratePerSqft}, ratePerRoom={data.ratePerRoom}, hourlyRate={data.hourlyRate}, flatRate={data.flatRate}"
    )
    logger.info(f"📋 Business name: {data.businessName}")
    logger.info(f"📋 All data fields: {data.model_dump()}")

    try:
        user = db.query(User).filter(User.firebase_uid == data.firebaseUid).first()
        if not user:
            logger.error(f"❌ User not found for firebase_uid: {data.firebaseUid}")
            raise HTTPException(status_code=404, detail="User not found")

        existing = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        )

        if existing:
            logger.info(
                f"📝 Current DB values: logo_url={existing.logo_url}, rate_per_sqft={existing.rate_per_sqft}, pricing_model={existing.pricing_model}"
            )

            # Only update fields that are explicitly provided (not None and not empty string)
            if is_provided(data.businessName):
                existing.business_name = data.businessName
            if is_provided(data.logoUrl):
                existing.logo_url = data.logoUrl
            if is_provided(data.signatureUrl):
                existing.signature_url = data.signatureUrl
            if data.onboardingComplete is not None:
                existing.onboarding_complete = data.onboardingComplete
                # CRITICAL FIX: Also update User.onboarding_completed to keep them synchronized
                user.onboarding_completed = data.onboardingComplete
                logger.info(f"🔄 Synchronized onboarding status to {data.onboardingComplete} for user {user.id} (existing config)")
            if data.formEmbeddingEnabled is not None:
                existing.form_embedding_enabled = data.formEmbeddingEnabled
            if is_provided(data.customFormsDomain):
                existing.custom_forms_domain = data.customFormsDomain
            if data.serviceAreas is not None:
                existing.service_areas = data.serviceAreas
            if is_provided(data.pricingModel):
                existing.pricing_model = data.pricingModel
            if data.meetingsRequired is not None:
                existing.meetings_required = data.meetingsRequired
            if is_provided(data.paymentHandling):
                existing.payment_handling = data.paymentHandling
            if is_provided(data.cancellationWindow):
                existing.cancellation_window = to_int(data.cancellationWindow) or 24
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
            if is_provided(data.suppliesProvided):
                existing.supplies_provided = data.suppliesProvided
            if data.availableSupplies is not None:
                existing.available_supplies = data.availableSupplies

            if is_provided(data.ratePerSqft):
                existing.rate_per_sqft = to_float(data.ratePerSqft)
            if is_provided(data.ratePerRoom):
                existing.rate_per_room = to_float(data.ratePerRoom)
            if is_provided(data.hourlyRate):
                existing.hourly_rate = to_float(data.hourlyRate)
            if is_provided(data.flatRate):
                existing.flat_rate = to_float(data.flatRate)
            if is_provided(data.flatRateSmall):
                existing.flat_rate_small = to_float(data.flatRateSmall)
            if is_provided(data.flatRateMedium):
                existing.flat_rate_medium = to_float(data.flatRateMedium)
            if is_provided(data.flatRateLarge):
                existing.flat_rate_large = to_float(data.flatRateLarge)
            if is_provided(data.minimumCharge):
                existing.minimum_charge = to_float(data.minimumCharge)
            if is_provided(data.cleaningTimePerSqft):
                existing.cleaning_time_per_sqft = to_int(data.cleaningTimePerSqft)

            # New three-category time estimation system
            if is_provided(data.timeSmallJob):
                existing.time_small_job = to_float(data.timeSmallJob)
            if is_provided(data.timeMediumJob):
                existing.time_medium_job = to_float(data.timeMediumJob)
            if is_provided(data.timeLargeJob):
                existing.time_large_job = to_float(data.timeLargeJob)
            if is_provided(data.cleanersSmallJob):
                existing.cleaners_small_job = to_int(data.cleanersSmallJob) or 1
            if is_provided(data.cleanersLargeJob):
                existing.cleaners_large_job = to_int(data.cleanersLargeJob) or 2
            if is_provided(data.bufferTime):
                existing.buffer_time = to_int(data.bufferTime) or 30

            if is_provided(data.premiumEveningWeekend):
                existing.premium_evening_weekend = to_float(data.premiumEveningWeekend)
            if is_provided(data.premiumDeepClean):
                existing.premium_deep_clean = to_float(data.premiumDeepClean)
            if is_provided(data.discountWeekly):
                existing.discount_weekly = to_float(data.discountWeekly)
            if is_provided(data.discountBiweekly):
                existing.discount_biweekly = to_float(data.discountBiweekly)
            if is_provided(data.discountMonthly):
                existing.discount_monthly = to_float(data.discountMonthly)
            if is_provided(data.discountLongTerm):
                existing.discount_long_term = to_float(data.discountLongTerm)

            if is_provided(data.firstCleaningDiscountType):
                existing.first_cleaning_discount_type = data.firstCleaningDiscountType
            if is_provided(data.firstCleaningDiscountValue):
                existing.first_cleaning_discount_value = to_float(
                    data.firstCleaningDiscountValue
                )

            if is_provided(data.addonWindows):
                existing.addon_windows = to_float(data.addonWindows)
            if is_provided(data.addonCarpets):
                existing.addon_carpets = to_float(data.addonCarpets)
            if is_provided(data.addonCarpetSmall):
                existing.addon_carpet_small = to_float(data.addonCarpetSmall)
            if is_provided(data.addonCarpetMedium):
                existing.addon_carpet_medium = to_float(data.addonCarpetMedium)
            if is_provided(data.addonCarpetLarge):
                existing.addon_carpet_large = to_float(data.addonCarpetLarge)

            if is_provided(data.paymentDueDays):
                existing.payment_due_days = to_int(data.paymentDueDays) or 15
            if is_provided(data.lateFeePercent):
                existing.late_fee_percent = to_float(data.lateFeePercent) or 1.5

            if data.standardInclusions is not None:
                existing.standard_inclusions = data.standardInclusions
            if data.standardExclusions is not None:
                existing.standard_exclusions = data.standardExclusions
            if data.customInclusions is not None:
                existing.custom_inclusions = data.customInclusions
            if data.customExclusions is not None:
                existing.custom_exclusions = data.customExclusions
            if is_provided(data.preferredUnits):
                existing.preferred_units = data.preferredUnits
            if data.customPackages is not None:
                existing.custom_packages = data.customPackages
            if data.activeTemplates is not None:
                logger.info(f"📝 Updating active_templates from {existing.active_templates} to {data.activeTemplates}")
                existing.active_templates = data.activeTemplates
            if data.acceptedFrequencies is not None:
                existing.accepted_frequencies = data.acceptedFrequencies
            if data.acceptedPaymentMethods is not None:
                existing.accepted_payment_methods = data.acceptedPaymentMethods
            
            # Brand color synchronization
            if is_provided(data.brandColor):
                existing.brand_color = data.brandColor
                # Also update the user's default brand color to keep them synchronized
                user.default_brand_color = data.brandColor
                logger.info(f"🎨 Synchronized brand color to {data.brandColor} for user {user.id}")

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
                form_embedding_enabled=data.formEmbeddingEnabled,
                custom_forms_domain=data.customFormsDomain,
                service_areas=data.serviceAreas,
                pricing_model=data.pricingModel,
                meetings_required=data.meetingsRequired,
                payment_handling=data.paymentHandling,
                cancellation_window=to_int(data.cancellationWindow) or 24,
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
                flat_rate_small=to_float(data.flatRateSmall),
                flat_rate_medium=to_float(data.flatRateMedium),
                flat_rate_large=to_float(data.flatRateLarge),
                minimum_charge=to_float(data.minimumCharge),
                cleaning_time_per_sqft=to_int(data.cleaningTimePerSqft),
                # New three-category time estimation system
                time_small_job=to_float(data.timeSmallJob),
                time_medium_job=to_float(data.timeMediumJob),
                time_large_job=to_float(data.timeLargeJob),
                cleaners_small_job=to_int(data.cleanersSmallJob) or 1,
                cleaners_large_job=to_int(data.cleanersLargeJob) or 2,
                buffer_time=to_int(data.bufferTime) or 30,
                premium_evening_weekend=to_float(data.premiumEveningWeekend),
                premium_deep_clean=to_float(data.premiumDeepClean),
                discount_weekly=to_float(data.discountWeekly),
                discount_biweekly=to_float(data.discountBiweekly),
                discount_monthly=to_float(data.discountMonthly),
                discount_long_term=to_float(data.discountLongTerm),
                first_cleaning_discount_type=data.firstCleaningDiscountType,
                first_cleaning_discount_value=to_float(data.firstCleaningDiscountValue),
                addon_windows=to_float(data.addonWindows),
                addon_carpets=to_float(data.addonCarpets),  # Legacy
                addon_carpet_small=to_float(data.addonCarpetSmall),
                addon_carpet_medium=to_float(data.addonCarpetMedium),
                addon_carpet_large=to_float(data.addonCarpetLarge),
                payment_due_days=to_int(data.paymentDueDays) or 15,
                late_fee_percent=to_float(data.lateFeePercent) or 1.5,
                standard_inclusions=data.standardInclusions,
                standard_exclusions=data.standardExclusions,
                custom_inclusions=data.customInclusions,
                custom_exclusions=data.customExclusions,
                preferred_units=data.preferredUnits,
                custom_packages=data.customPackages,
                active_templates=data.activeTemplates,
                accepted_frequencies=data.acceptedFrequencies or ["one-time", "daily", "2x-per-week", "3x-per-week", "weekly", "bi-weekly", "monthly"],
                accepted_payment_methods=data.acceptedPaymentMethods or [],
                brand_color=data.brandColor or "#00C4B4",  # Default brand color
            )
            
            logger.info(f"📝 Creating new config with active_templates: {data.activeTemplates}")
            
            # Also update the user's default brand color to keep them synchronized
            if is_provided(data.brandColor):
                user.default_brand_color = data.brandColor
                logger.info(f"🎨 Set brand color to {data.brandColor} for new config user {user.id}")
            
            db.add(config)
            db.commit()

        # CRITICAL FIX: Ensure both User.onboarding_completed and BusinessConfig.onboarding_complete are synchronized
        # This prevents users from losing onboarding progress when switching devices
        if data.onboardingComplete is not None:
            user.onboarding_completed = data.onboardingComplete
            # Also ensure BusinessConfig is updated if it exists
            if config:
                config.onboarding_complete = data.onboardingComplete
            logger.info(f"🔄 Synchronized onboarding status to {data.onboardingComplete} for user {user.id}")
        
        db.commit()

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
    if (
        not firebase_uid
        or len(firebase_uid) > 128
        or not firebase_uid.replace("-", "").replace("_", "").isalnum()
    ):
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

    return {
        "businessName": config.business_name,
        "logoKey": config.logo_url,  # The R2 key
        "logoUrl": logo_presigned_url,  # Presigned URL for display
        "customFormsDomain": config.custom_forms_domain,
        "signatureKey": config.signature_url,  # The R2 key
        "signatureUrl": signature_presigned_url,  # Presigned URL for display
        "pricingModel": config.pricing_model,
        "meetingsRequired": config.meetings_required,
        "paymentHandling": config.payment_handling,
        "cancellationWindow": config.cancellation_window,
        "daySchedules": config.day_schedules,
        "offWorkPeriods": config.off_work_periods,
        "suppliesProvided": config.supplies_provided,
        "ratePerSqft": config.rate_per_sqft,
        "ratePerRoom": config.rate_per_room,
        "hourlyRate": config.hourly_rate,
        "flatRate": config.flat_rate,
        "flatRateSmall": config.flat_rate_small,
        "flatRateMedium": config.flat_rate_medium,
        "flatRateLarge": config.flat_rate_large,
        "minimumCharge": config.minimum_charge,
        "cleaningTimePerSqft": config.cleaning_time_per_sqft,
        "timeSmallJob": config.time_small_job,
        "timeMediumJob": config.time_medium_job,
        "timeLargeJob": config.time_large_job,
        "cleanersSmallJob": config.cleaners_small_job,
        "cleanersLargeJob": config.cleaners_large_job,
        "bufferTime": config.buffer_time,
        "premiumEveningWeekend": config.premium_evening_weekend,
        "premiumDeepClean": config.premium_deep_clean,
        "discountWeekly": config.discount_weekly,
        "discountBiweekly": config.discount_biweekly,
        "discountMonthly": config.discount_monthly,
        "discountLongTerm": config.discount_long_term,
        "firstCleaningDiscountType": config.first_cleaning_discount_type,
        "firstCleaningDiscountValue": config.first_cleaning_discount_value,
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,
        "paymentDueDays": config.payment_due_days,
        "lateFeePercent": config.late_fee_percent,
        "standardInclusions": config.standard_inclusions,
        "standardExclusions": config.standard_exclusions,
        "customInclusions": config.custom_inclusions,
        "customExclusions": config.custom_exclusions,
        "preferredUnits": config.preferred_units,
        "addonCarpetSmall": config.addon_carpet_small,
        "addonCarpetMedium": config.addon_carpet_medium,
        "addonCarpetLarge": config.addon_carpet_large,
        "customPackages": config.custom_packages,
        "brandColor": config.brand_color,  # Brand color for business settings
        "acceptedFrequencies": config.accepted_frequencies or ["one-time", "daily", "2x-per-week", "3x-per-week", "weekly", "bi-weekly", "monthly"],
        "acceptedPaymentMethods": config.accepted_payment_methods or [],
    }


@router.get("/public/branding/{firebase_uid}")
def get_public_branding(
    firebase_uid: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to get business branding (logo, name) for client-facing forms.
    No authentication required - accessed via shareable form links.
    Supports custom domain validation for security.
    """
    logger.info(f"📥 Getting public branding for firebase_uid: {firebase_uid}")

    # Custom domain security validation
    if hasattr(request.state, 'is_custom_domain') and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (not hasattr(request.state, 'custom_domain_user_uid') or 
            request.state.custom_domain_user_uid != firebase_uid):
            logger.warning(
                f"🚫 Custom domain security violation in branding: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match requested user {firebase_uid}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: Custom domain does not match requested user"
            )
        logger.info(f"✅ Custom domain validation passed for branding {firebase_uid}")

    # Validate firebase_uid format to prevent injection
    if (
        not firebase_uid
        or len(firebase_uid) > 128
        or not firebase_uid.replace("-", "").replace("_", "").isalnum()
    ):
        raise HTTPException(status_code=400, detail="Invalid business identifier")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.error(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

    # Return default branding if no config exists
    if not config:
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
    return {
        "businessName": config.business_name,
        "logoUrl": logo_presigned_url,
        "brandColor": config.brand_color,  # Brand color for intake forms
        "plan": user.plan,  # Include plan for conditional badge display
    }


@router.get("/public/addons/{firebase_uid}")
def get_public_addons(
    firebase_uid: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to get business addon services for client-facing forms.
    No authentication required - accessed via shareable form links.
    Supports custom domain validation for security.
    """
    logger.info(f"📥 Getting public addons for firebase_uid: {firebase_uid}")

    # Custom domain security validation
    if hasattr(request.state, 'is_custom_domain') and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (not hasattr(request.state, 'custom_domain_user_uid') or 
            request.state.custom_domain_user_uid != firebase_uid):
            logger.warning(
                f"🚫 Custom domain security violation in addons: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match requested user {firebase_uid}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: Custom domain does not match requested user"
            )
        logger.info(f"✅ Custom domain validation passed for addons {firebase_uid}")

    # Validate firebase_uid format to prevent injection
    if (
        not firebase_uid
        or len(firebase_uid) > 128
        or not firebase_uid.replace("-", "").replace("_", "").isalnum()
    ):
        raise HTTPException(status_code=400, detail="Invalid business identifier")

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.error(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()

    # Return empty addons if no config exists
    if not config:
        return {
            "customAddons": [],
            "addonWindows": None,
            "addonCarpets": None,  # Legacy - deprecated
            "addonCarpetSmall": None,
            "addonCarpetMedium": None,
            "addonCarpetLarge": None,
            "discountWeekly": None,
            "discountBiweekly": None,
            "discountMonthly": None,
        }
    return {
        "customAddons": config.custom_addons or [],
        "addonWindows": config.addon_windows,
        "addonCarpets": config.addon_carpets,  # Legacy - deprecated
        "addonCarpetSmall": config.addon_carpet_small,
        "addonCarpetMedium": config.addon_carpet_medium,
        "addonCarpetLarge": config.addon_carpet_large,
        "discountWeekly": config.discount_weekly,
        "discountBiweekly": config.discount_biweekly,
        "discountMonthly": config.discount_monthly,
        "acceptedFrequencies": config.accepted_frequencies or ["one-time", "daily", "2x-per-week", "3x-per-week", "weekly", "bi-weekly", "monthly"],
    }


@router.get("/{firebase_uid}/public-info")
def get_public_business_info(
    firebase_uid: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get public business information including working hours and schedules (for business-aware calendar)
    No authentication required - accessed via client forms and scheduling components.
    Supports custom domain validation for security.
    """
    logger.info(f"📥 Getting public business info for firebase_uid: {firebase_uid}")

    # Custom domain security validation
    if hasattr(request.state, 'is_custom_domain') and request.state.is_custom_domain:
        # If this is a custom domain request, validate that the domain belongs to the requested user
        if (not hasattr(request.state, 'custom_domain_user_uid') or 
            request.state.custom_domain_user_uid != firebase_uid):
            logger.warning(
                f"🚫 Custom domain security violation in public info: Domain user {getattr(request.state, 'custom_domain_user_uid', 'unknown')} "
                f"does not match requested user {firebase_uid}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: Custom domain does not match requested user"
            )
        logger.info(f"✅ Custom domain validation passed for public info {firebase_uid}")

    # Validate firebase_uid format to prevent injection
    if (
        not firebase_uid
        or len(firebase_uid) > 128
        or not firebase_uid.replace("-", "").replace("_", "").isalnum()
    ):
        raise HTTPException(status_code=400, detail="Invalid business identifier")

    # Find user by firebase_uid
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        logger.warning(f"❌ User not found for firebase_uid: {firebase_uid}")
        raise HTTPException(status_code=404, detail="Business not found")

    # Get business config
    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        logger.warning(f"❌ Business config not found for user_id: {user.id}")
        raise HTTPException(status_code=404, detail="Business configuration not found")

    # Parse working hours and days with defaults
    working_hours = {"start": "9:00", "end": "17:00"}  # Default 9 AM - 5 PM
    working_days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    ]  # Default weekdays
    day_schedules = {}
    off_work_periods = []

    # Use the stored working_hours, working_days, day_schedules, and off_work_periods
    if config.working_hours:
        try:
            if isinstance(config.working_hours, dict):
                working_hours = config.working_hours
            elif isinstance(config.working_hours, str):
                import json

                working_hours = json.loads(config.working_hours)
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse working_hours for {firebase_uid}: {e}")

    if config.working_days:
        try:
            if isinstance(config.working_days, list):
                working_days = config.working_days
            elif isinstance(config.working_days, str):
                import json

                working_days = json.loads(config.working_days)
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse working_days for {firebase_uid}: {e}")

    if config.day_schedules:
        try:
            if isinstance(config.day_schedules, dict):
                day_schedules = config.day_schedules
            elif isinstance(config.day_schedules, str):
                import json

                day_schedules = json.loads(config.day_schedules)
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse day_schedules for {firebase_uid}: {e}")

    if config.off_work_periods:
        try:
            if isinstance(config.off_work_periods, list):
                off_work_periods = config.off_work_periods
            elif isinstance(config.off_work_periods, str):
                import json

                off_work_periods = json.loads(config.off_work_periods)
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse off_work_periods for {firebase_uid}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse off_work_periods for {firebase_uid}: {e}")

    return {
        "business_name": config.business_name or "Business",
        "working_hours": working_hours,
        "working_days": working_days,
        "day_schedules": day_schedules,
        "off_work_periods": off_work_periods,
    }

