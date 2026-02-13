"""
PDF Contract Generation using Playwright (Chromium)
Generates professional contracts from HTML templates and stores them privately in R2
"""
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from ..models import User, BusinessConfig, Client, Contract
from ..auth import get_current_user
from .upload import generate_presigned_url, get_r2_client
from ..config import R2_BUCKET_NAME, FRONTEND_URL
from ..rate_limiter import create_rate_limiter, rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contracts PDF"])

# Rate limiters for contract download
rate_limit_download_per_ip = create_rate_limiter(
    limit=5,
    window_seconds=60,
    key_prefix="contract_download_ip",
    use_ip=True
)

async def rate_limit_per_contract(request: Request, contract_id: int):
    """Rate limit by contract ID - 3 downloads per minute per contract"""
    await rate_limit_dependency(
        request=request,
        limit=3,
        window_seconds=60,
        key_prefix=f"contract_download_id_{contract_id}",
        use_ip=False
    )

class ContractGenerateRequest(BaseModel):
    clientId: int
    ownerUid: str
    formData: dict
    clientSignature: Optional[str] = None  # Base64 signature from client

def calculate_estimated_hours(config: BusinessConfig, property_size: int) -> float:
    """Calculate estimated hours using the new three-category system or fallback to legacy"""

    # Try new three-category system first
    if config.time_small_job or config.time_medium_job or config.time_large_job:
        if property_size < 1500 and config.time_small_job:
            # Small: < 1500 sqft
            return config.time_small_job
        elif 1500 <= property_size <= 2500 and config.time_medium_job:
            # Medium: 1500-2500 sqft
            return config.time_medium_job
        elif property_size > 2500 and config.time_large_job:
            # Large: > 2500 sqft
            return config.time_large_job
        else:
            # Fallback if specific category not configured
            if property_size < 1500:
                return config.time_small_job or config.time_medium_job or config.time_large_job or 1.5
            elif property_size > 2500:
                return config.time_large_job or config.time_medium_job or config.time_small_job or 4.0
            else:  # 1500-2500 range
                return config.time_medium_job or config.time_large_job or config.time_small_job or 2.5

    # Fallback to legacy system
    elif config.cleaning_time_per_sqft and property_size:
        return (property_size / 1000) * (config.cleaning_time_per_sqft / 60)

    # Final fallback to realistic estimates
    else:
        if property_size <= 800:
            return 1.5  # Small apartment/condo: 1.5 hours
        elif property_size <= 1500:
            return 2.5  # Medium home: 2.5 hours
        elif property_size <= 2500:
            return 3.5  # Large home: 3.5 hours
        else:
            return 4.0  # Very large home: max 4 hours

def _get_selected_package_details(config: BusinessConfig, form_data: dict) -> dict:
    """Get details of the selected package for quote display"""
    selected_package_id = form_data.get("selectedPackage")
    if not selected_package_id or not config.custom_packages:
        return None
    
    for package in config.custom_packages:
        if package.get("id") == selected_package_id:
            return {
                "id": package.get("id"),
                "name": package.get("name", "Custom Package"),
                "description": package.get("description", ""),
                "included": package.get("included", []),
                "duration": package.get("duration", 0),
                "priceType": package.get("priceType", "flat"),
                "price": package.get("price"),
                "priceMin": package.get("priceMin"),
                "priceMax": package.get("priceMax"),
            }
    
    return None

def calculate_quote(config: BusinessConfig, form_data: dict) -> dict:
    """Calculate quote based on business config and form data"""
    import logging
    logger = logging.getLogger(__name__)

    pricing_model = config.pricing_model
    property_size = int(form_data.get("squareFootage", 0) or 0)
    num_rooms = int(form_data.get("numberOfOffices", 0) or form_data.get("numberOfRooms", 0) or 0)
    frequency = form_data.get("cleaningFrequency", "Weekly")
    logger.info(f"📊 Config rates - sqft: {config.rate_per_sqft}, hourly: {config.hourly_rate}, flat: {config.flat_rate}")
    logger.info(f"📊 Pricing model: {pricing_model}, property_size: {property_size}, num_rooms: {num_rooms}, frequency: {frequency}")

    base_price = 0.0
    estimated_hours = 0.0

    # Calculate base price based on pricing model
    if pricing_model == "sqft" and config.rate_per_sqft:
        base_price = property_size * config.rate_per_sqft
        # Use new three-category time estimation system
        estimated_hours = calculate_estimated_hours(config, property_size)
    elif pricing_model == "hourly" and config.hourly_rate:
        # Use new three-category time estimation system
        estimated_hours = calculate_estimated_hours(config, property_size)
        base_price = estimated_hours * config.hourly_rate
    elif pricing_model == "packages":
        # Custom packages pricing
        selected_package_id = form_data.get("selectedPackage")
        if selected_package_id and config.custom_packages:
            # Find the selected package
            selected_package = None
            for package in config.custom_packages:
                if package.get("id") == selected_package_id:
                    selected_package = package
                    break
            
            if selected_package:
                # Calculate price based on package pricing type
                if selected_package.get("priceType") == "flat" and selected_package.get("price"):
                    base_price = float(selected_package["price"])
                elif selected_package.get("priceType") == "range":
                    # For range pricing, use the minimum price as base (can be adjusted later)
                    price_min = selected_package.get("priceMin", 0)
                    price_max = selected_package.get("priceMax", 0)
                    if price_min and price_max:
                        # Use average of range for quote calculation
                        base_price = (float(price_min) + float(price_max)) / 2
                    elif price_min:
                        base_price = float(price_min)
                    elif price_max:
                        base_price = float(price_max)
                else:
                    # Quote-based pricing - set flag for manual quote
                    base_price = 0.0
                
                # Use package duration for time estimation
                if selected_package.get("duration"):
                    estimated_hours = float(selected_package["duration"]) / 60.0  # Convert minutes to hours
                else:
                    # Fallback to standard time estimation
                    estimated_hours = calculate_estimated_hours(config, property_size)
                
                logger.info(f"📦 Package pricing - selected: {selected_package.get('name')}, price: ${base_price}, duration: {estimated_hours}h")
            else:
                logger.warning(f"⚠️ Selected package {selected_package_id} not found in config")
        else:
            logger.warning(f"⚠️ No package selected or no packages configured for packages pricing model")
    elif pricing_model == "flat":
        # Flat-fee pricing can be configured either as a single legacy flat_rate
        # or as 3 size-based rates (small/medium/large).
        # Prefer the size-based rates when available.
        def _pick_size_flat_rate() -> float:
            if property_size < 1000:
                return config.flat_rate_small or 0.0
            elif 1500 <= property_size <= 2500:
                return config.flat_rate_medium or 0.0
            elif property_size > 2500:
                return config.flat_rate_large or 0.0
            # Gap ranges: choose the closest configured value.
            if property_size < 1500:
                return config.flat_rate_small or config.flat_rate_medium or config.flat_rate_large or 0.0
            return config.flat_rate_medium or config.flat_rate_large or config.flat_rate_small or 0.0

        base_price = _pick_size_flat_rate() or (config.flat_rate or 0.0)
        if base_price:
            # Use new three-category time estimation system
            estimated_hours = calculate_estimated_hours(config, property_size)

    # If no pricing model matched or base_price is still 0, try fallbacks
    if base_price == 0:
        logger.warning(f"⚠️ Base price is 0 after initial calculation - pricing_model: {pricing_model}, trying fallback rates")
        # Try each rate type as fallback
        if (config.flat_rate_small or config.flat_rate_medium or config.flat_rate_large) and property_size > 0:
            # Use size-based flat rates as first fallback when property size is known
            if property_size < 1000:
                base_price = config.flat_rate_small or 0.0
            elif 1500 <= property_size <= 2500:
                base_price = config.flat_rate_medium or 0.0
            elif property_size > 2500:
                base_price = config.flat_rate_large or 0.0
            else:
                base_price = config.flat_rate_small or config.flat_rate_medium or config.flat_rate_large or 0.0
            estimated_hours = calculate_estimated_hours(config, property_size) if base_price else 0.0
        elif config.flat_rate and config.flat_rate > 0:
            base_price = config.flat_rate
            estimated_hours = 2
        elif config.hourly_rate and config.hourly_rate > 0:
            # Realistic time estimates for fallback
            if property_size > 0:
                if property_size <= 800:
                    estimated_hours = 1.5
                elif property_size <= 1500:
                    estimated_hours = 2.5
                elif property_size <= 2500:
                    estimated_hours = 3.5
                else:
                    estimated_hours = 4.0
            else:
                estimated_hours = 2.0  # Default when no property size
            base_price = estimated_hours * config.hourly_rate
        elif config.rate_per_sqft and config.rate_per_sqft > 0 and property_size > 0:
            base_price = property_size * config.rate_per_sqft
            # Realistic time estimates based on property size
            if property_size <= 800:
                estimated_hours = 1.5
            elif property_size <= 1500:
                estimated_hours = 2.5
            elif property_size <= 2500:
                estimated_hours = 3.5
            else:
                estimated_hours = 4.0
    # Apply minimum charge
    if config.minimum_charge and base_price < config.minimum_charge:
        logger.info(f"📊 Applying minimum charge: ${config.minimum_charge} (was ${base_price})")
        base_price = config.minimum_charge
    
    logger.info(f"📊 Base price after all calculations: ${base_price}, estimated_hours: {estimated_hours}")
    # Calculate add-ons
    addon_total = 0.0
    addon_details = []
    selected_addons = form_data.get("selectedAddons", [])
    addon_quantities = form_data.get("addonQuantities", {})
    if selected_addons:
        # Process standard add-ons
        if "addon_windows" in selected_addons and config.addon_windows:
            quantity = addon_quantities.get("addon_windows", 1)
            addon_price = config.addon_windows * quantity
            addon_total += addon_price
            addon_details.append({
                "name": "Window Cleaning",
                "quantity": quantity,
                "unit_price": config.addon_windows,
                "total_price": addon_price,
                "pricing_metric": "per window"
            })
        # Size-based carpet cleaning addons
        if "addon_carpet_small" in selected_addons and config.addon_carpet_small:
            quantity = addon_quantities.get("addon_carpet_small", 1)
            addon_price = config.addon_carpet_small * quantity
            addon_total += addon_price
            addon_details.append({
                "name": "Small Carpet Cleaning",
                "quantity": quantity,
                "unit_price": config.addon_carpet_small,
                "total_price": addon_price,
                "pricing_metric": "per carpet"
            })
        if "addon_carpet_medium" in selected_addons and config.addon_carpet_medium:
            quantity = addon_quantities.get("addon_carpet_medium", 1)
            addon_price = config.addon_carpet_medium * quantity
            addon_total += addon_price
            addon_details.append({
                "name": "Medium Carpet Cleaning",
                "quantity": quantity,
                "unit_price": config.addon_carpet_medium,
                "total_price": addon_price,
                "pricing_metric": "per carpet"
            })
        if "addon_carpet_large" in selected_addons and config.addon_carpet_large:
            quantity = addon_quantities.get("addon_carpet_large", 1)
            addon_price = config.addon_carpet_large * quantity
            addon_total += addon_price
            addon_details.append({
                "name": "Large Carpet Cleaning",
                "quantity": quantity,
                "unit_price": config.addon_carpet_large,
                "total_price": addon_price,
                "pricing_metric": "per carpet"
            })
        # Legacy carpet addon for backward compatibility
        if "addon_carpets" in selected_addons and config.addon_carpets:
            quantity = addon_quantities.get("addon_carpets", 1)
            addon_price = config.addon_carpets * quantity
            addon_total += addon_price
            addon_details.append({
                "name": "Carpet Cleaning",
                "quantity": quantity,
                "unit_price": config.addon_carpets,
                "total_price": addon_price,
                "pricing_metric": "per sq ft"
            })
        # Process custom add-ons
        if config.custom_addons:
            for custom_addon in config.custom_addons:
                addon_id = custom_addon.get("id") or f"custom_{custom_addon.get('name', '')}"
                if addon_id in selected_addons:
                    unit_price = float(custom_addon.get("price", 0))
                    pricing_metric = custom_addon.get("pricingMetric", "per service")

                    # For "per service" or "flat rate", quantity is always 1
                    if pricing_metric in ["per service", "flat rate"]:
                        quantity = 1
                    else:
                        quantity = addon_quantities.get(addon_id, 1)

                    addon_price = unit_price * quantity
                    addon_total += addon_price
                    addon_details.append({
                        "name": custom_addon.get("name", "Custom Add-on"),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": addon_price,
                        "pricing_metric": pricing_metric
                    })
    logger.info(f"📊 Total add-ons: ${addon_total}")

    # Apply frequency discount to base price only (not add-ons)
    discount_percent = 0
    if frequency == "Weekly" and config.discount_weekly:
        discount_percent = config.discount_weekly
    elif frequency == "Bi-weekly" and config.discount_biweekly:
        discount_percent = config.discount_biweekly
    elif frequency == "Monthly" and config.discount_monthly:
        discount_percent = config.discount_monthly
    elif frequency == "Long-term" and config.discount_long_term:
        discount_percent = config.discount_long_term

    discount_amount = base_price * (discount_percent / 100) if discount_percent else 0
    discounted_base_price = base_price - discount_amount

    # Apply first cleaning discount ONLY on the first visit.
    # This is controlled by a flag sent from the client form/quote preview.
    is_first_cleaning = bool(form_data.get("isFirstCleaning", False))
    first_cleaning_discount_amount = 0.0
    first_cleaning_discount_type = None
    first_cleaning_discount_value = None

    logger.info(f"🔍 First cleaning discount check - isFirstCleaning: {is_first_cleaning}, "
                f"config.first_cleaning_discount_value: {getattr(config, 'first_cleaning_discount_value', None)}, "
                f"config.first_cleaning_discount_type: {getattr(config, 'first_cleaning_discount_type', None)}")

    if is_first_cleaning and getattr(config, "first_cleaning_discount_value", None):
        first_cleaning_discount_type = getattr(config, "first_cleaning_discount_type", None) or "percent"
        first_cleaning_discount_value = float(getattr(config, "first_cleaning_discount_value") or 0)

        logger.info(f"💰 Applying first cleaning discount - type: {first_cleaning_discount_type}, value: {first_cleaning_discount_value}, discounted_base_price: ${discounted_base_price:.2f}")

        if first_cleaning_discount_type == "fixed":
            first_cleaning_discount_amount = min(first_cleaning_discount_value, discounted_base_price)
        else:
            # Default to percent
            first_cleaning_discount_amount = discounted_base_price * (first_cleaning_discount_value / 100.0)

        logger.info(f"💰 First cleaning discount calculated: ${first_cleaning_discount_amount:.2f}")

        discounted_base_price = max(0.0, discounted_base_price - first_cleaning_discount_amount)

    final_price = discounted_base_price + addon_total

    # Determine number of cleaners
    cleaners = config.cleaners_small_job or 1
    if property_size > 2000:
        cleaners = config.cleaners_large_job or 2

    # Calculate term duration total if provided (for recurring services)
    term_duration = form_data.get("contractTermDuration")
    term_unit = form_data.get("contractTermUnit", "Months")
    total_term_rate = None
    service_occurrences = None

    # Check if this is a one-time service (no contract duration needed)
    one_time_frequencies = ["One-time", "One-time deep clean", "Per turnover", "On-demand", "As needed"]
    is_one_time = frequency in one_time_frequencies

    if term_duration and not is_one_time:
        try:
            duration_value = int(term_duration)
            # Convert term to months
            duration_months = duration_value if term_unit == "Months" else duration_value * 12

            # Calculate number of service occurrences based on frequency
            if frequency == "Daily":
                # Approximate 22 working days per month
                service_occurrences = duration_months * 22
            elif frequency == "Weekly":
                service_occurrences = duration_months * 4
            elif frequency == "Bi-weekly":
                service_occurrences = duration_months * 2
            elif frequency == "Monthly":
                service_occurrences = duration_months
            elif frequency == "Twice daily":
                service_occurrences = duration_months * 44
            elif frequency == "Multiple times daily":
                service_occurrences = duration_months * 66  # 3 times per day
            elif frequency == "After each shift":
                service_occurrences = duration_months * 44  # 2 shifts per day
            elif frequency == "Weekly deep clean":
                service_occurrences = duration_months * 4
            else:
                service_occurrences = duration_months * 4  # Default to weekly

            total_term_rate = final_price * service_occurrences
        except (ValueError, TypeError):
            pass

    # Ensure minimum values for display
    if estimated_hours < 1:
        estimated_hours = 1.0

    # If still no price, set a flag for "quote pending"
    quote_pending = base_price == 0 and final_price == 0
    
    logger.info(f"📊 Final quote calculation - base_price: ${base_price}, discount_amount: ${discount_amount}, addon_total: ${addon_total}, final_price: ${final_price}, quote_pending: {quote_pending}")
    
    # Special handling for packages pricing model
    if pricing_model == "packages":
        selected_package_id = form_data.get("selectedPackage")
        if selected_package_id and config.custom_packages:
            # Find the selected package
            for package in config.custom_packages:
                if package.get("id") == selected_package_id:
                    # If package requires quote, set quote_pending flag
                    if package.get("priceType") == "quote":
                        quote_pending = True
                    break
        else:
            # No package selected - quote pending
            quote_pending = True
    return {
        "base_price": round(base_price, 2),
        "discount_percent": discount_percent,
        "discount_amount": round(discount_amount, 2),
        "first_cleaning_discount_type": first_cleaning_discount_type,
        "first_cleaning_discount_value": round(first_cleaning_discount_value, 2) if first_cleaning_discount_value is not None else None,
        "first_cleaning_discount_amount": round(first_cleaning_discount_amount, 2),
        "addon_amount": round(addon_total, 2),
        "addon_details": addon_details,
        "final_price": round(final_price, 2),
        "estimated_hours": round(estimated_hours, 1),
        "cleaners": cleaners,
        "pricing_model": pricing_model,
        "frequency": frequency,
        "term_duration": term_duration,
        "term_unit": term_unit,
        "total_term_rate": round(total_term_rate, 2) if total_term_rate else None,
        "service_occurrences": service_occurrences,
        "quote_pending": quote_pending,
        "selected_package": _get_selected_package_details(config, form_data) if pricing_model == "packages" else None,
    }

async def generate_contract_html(
    business_config: BusinessConfig,
    client: Client,
    form_data: dict,
    quote: dict,
    db: Session,
    client_signature: Optional[str] = None,
    provider_signature: Optional[str] = None,
    contract_created_at: Optional[datetime] = None,
    contract_public_id: Optional[str] = None
) -> str:
    """Generate HTML for the contract"""

    # Debug logging for business config pricing
    logger.info(f"🖼️ Business config branding - name: {business_config.business_name}, logo: {business_config.logo_url}")

    # Warn if all pricing fields are NULL
    if not any([business_config.rate_per_sqft, business_config.hourly_rate, business_config.flat_rate]):
        logger.warning(f"⚠️ ALL PRICING FIELDS ARE NULL for user_id: {business_config.user_id} - user needs to update pricing in Settings")

    # Debug logging for signatures - INPUT
    if client_signature:
        pass  # Client signature provided
    if provider_signature:
        pass  # Provider signature provided
    # Get branding
    business_name = business_config.business_name or "Cleaning Service"
    logo_url = None
    signature_url = None

    logger.info(f"🏢 Business config - name: {business_name}, logo_url key: {business_config.logo_url}")

    # Download and convert logo to base64 for Playwright
    if business_config.logo_url:
        try:
            # Check if logo_url is already a full URL (shouldn't be, but handle it)
            if business_config.logo_url.startswith('http'):
                presigned_logo_url = business_config.logo_url
            else:
                presigned_logo_url = generate_presigned_url(business_config.logo_url)
            logo_url = await download_image_as_base64(presigned_logo_url)
            if logo_url:
                pass  # Logo successfully downloaded
            else:
                logger.warning(f"⚠️ Logo download returned None for URL: {presigned_logo_url[:100]}...")
        except Exception as e:
            logger.error(f"❌ Failed to generate/download logo: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    else:
        pass  # No logo URL configured
    # Download and convert provider signature to base64
    if provider_signature:
        # Check if it's already base64 or a URL
        if provider_signature.startswith("data:image"):
            signature_url = provider_signature
        elif provider_signature.startswith("http"):
            signature_url = await download_image_as_base64(provider_signature)
            if signature_url:
                pass  # Signature successfully downloaded
        else:
            signature_url = provider_signature
    elif business_config.signature_url:
        try:
            presigned_sig_url = generate_presigned_url(business_config.signature_url)
            signature_url = await download_image_as_base64(presigned_sig_url)
            if signature_url:
                pass  # Signature successfully downloaded
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate signature URL: {e}")

    # Download and convert client signature to base64
    if client_signature:
        if client_signature.startswith("data:image"):
            # Already base64, use as-is
            pass
        elif client_signature.startswith("http"):
            # Download from URL
            logger.info(f"📥 Downloading client signature from URL: {client_signature[:100]}...")
            client_signature_b64 = await download_image_as_base64(client_signature)
            if client_signature_b64:
                client_signature = client_signature_b64
            else:
                logger.warning("⚠️ Failed to download client signature from URL")
        # else: assume it's already in correct format
    else:
        pass  # No client signature provided
    # Contract details - use passed date or current date for new contracts
    base_date = contract_created_at or datetime.now()
    contract_date = base_date.strftime("%B %d, %Y")
    
    # Use secure random contract ID instead of sequential numbering
    # Format: CLN-{first 8 chars of UUID} (e.g., CLN-A7B3C9D2)
    # This prevents enumeration attacks and provides collision-resistant IDs
    contract_number = f"CLN-{contract_public_id[:8].upper()}" if contract_public_id else f"CLN-DRAFT-{base_date.strftime('%Y%m%d')}"

    # Smart start date logic based on service type
    frequency = quote["frequency"]
    one_time_frequencies = ["One-time", "One-time deep clean", "Per turnover", "On-demand", "As needed", "one-time"]
    is_recurring = frequency not in one_time_frequencies

    if is_recurring:
        # Recurring contracts: billing starts on signing date
        start_date = base_date.strftime("%B %d, %Y")
        start_date_note = "Agreement effective immediately upon signing. First service will be scheduled separately."
    else:
        # One-time/deep cleans: align with service date (typically 7 days out)
        start_date = (base_date + timedelta(days=7)).strftime("%B %d, %Y")
        start_date_note = "Agreement effective on scheduled service date."

    payment_due_days = business_config.payment_due_days or 15
    late_fee = business_config.late_fee_percent or 1.5
    cancellation_window = business_config.cancellation_window or 24

    # Client info
    client_name = client.contact_name or client.business_name
    client_email = client.email or ""
    client_phone = client.phone or ""
    client_address = form_data.get("billingAddress", "") or form_data.get("address", "")

    # Property details
    property_size = form_data.get("squareFootage", "N/A")
    property_type = client.property_type or "Commercial"

    # Property shots (client-uploaded photos)
    property_shots_keys = form_data.get("propertyShots") if form_data else None
    if isinstance(property_shots_keys, str):
        property_shots_keys = [property_shots_keys]
    if not isinstance(property_shots_keys, list):
        property_shots_keys = []

    # Property shots are no longer embedded in PDFs - they are sent to provider via email
    property_shots_b64 = []

    # Special requests from client form
    special_requests = form_data.get("specialRequests", "").strip() if form_data.get("specialRequests") else None
    if special_requests == "":
        special_requests = None

    # Service details (frequency already extracted above for start_date logic)
    # Combine standard and custom inclusions/exclusions
    standard_inclusions = business_config.standard_inclusions or []
    custom_inclusions = business_config.custom_inclusions or []
    inclusions = standard_inclusions + custom_inclusions

    standard_exclusions = business_config.standard_exclusions or []
    custom_exclusions = business_config.custom_exclusions or []
    exclusions = standard_exclusions + custom_exclusions

    # Build inclusions/exclusions HTML
    inclusions_html = "".join([f"<li>{item}</li>" for item in inclusions]) if inclusions else "<li>Standard cleaning services</li>"
    exclusions_html = "".join([f"<li>{item}</li>" for item in exclusions]) if exclusions else "<li>None specified</li>"
    logger.info(f"🖊️ [BEFORE TEMPLATE] Client client_signature: {'SET (' + str(len(client_signature)) + ' chars)' if client_signature else 'NOT SET (None)'}")
    if signature_url:
        logger.info(f"🖊️ [BEFORE TEMPLATE] Provider sig is base64: {signature_url.startswith('data:image')}")
    if client_signature:
        logger.info(f"🖊️ [BEFORE TEMPLATE] Client sig is base64: {client_signature.startswith('data:image')}")

    # Prepare signature HTML fragments
    provider_signature_html = ""
    if signature_url:
        provider_signature_html = f"<img src='{signature_url}' alt='Provider Signature'>"
    else:
        provider_signature_html = ""
    
    client_signature_html = ""
    if client_signature:
        client_signature_html = f"<img src='{client_signature}' alt='Client Signature'>"
    else:
        client_signature_html = ""
    
    # Format accepted payment methods
    accepted_methods = "check, bank transfer, or other agreed-upon methods"  # Default
    if business_config.accepted_payment_methods and len(business_config.accepted_payment_methods) > 0:
        # Map internal payment method IDs to display names
        payment_method_names = {
            "cash": "Cash",
            "check": "Check",
            "card": "Credit/Debit Card",
            "venmo": "Venmo",
            "paypal": "PayPal",
            "zelle": "Zelle",
            "bank-transfer": "Bank Transfer",
            "square": "Square"
        }
        
        # Convert payment method IDs to display names
        method_list = [
            payment_method_names.get(method, method.title())
            for method in business_config.accepted_payment_methods
        ]
        
        # Format as comma-separated list with "and" before last item
        if len(method_list) == 1:
            accepted_methods = method_list[0]
        elif len(method_list) == 2:
            accepted_methods = f"{method_list[0]} and {method_list[1]}"
        else:
            accepted_methods = ", ".join(method_list[:-1]) + f", and {method_list[-1]}"
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Agreement - {contract_number}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: 'Poppins', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 10pt;
            line-height: 1.7;
            color: #0A2540;
            background: white;
            padding: 50px 60px;
        }}
        .header {{
            display: flex;
            justify-content: flex-end;
            align-items: flex-start;
            margin-bottom: 40px;
        }}
        .logo-section {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .logo {{
            max-height: 40px;
            max-width: 150px;
            object-fit: contain;
        }}
        .company-name {{
            font-size: 14pt;
            font-weight: 600;
            color: #0A2540;
        }}
        .contract-title {{
            font-size: 22pt;
            font-weight: 600;
            color: #0A2540;
            margin-bottom: 20px;
        }}
        .contract-intro {{
            font-size: 10pt;
            color: #425466;
            margin-bottom: 30px;
            line-height: 1.8;
        }}
        .contract-intro strong {{
            color: #0A2540;
        }}
        .section {{
            margin-bottom: 28px;
        }}
        .section-title {{
            font-size: 11pt;
            font-weight: 600;
            color: #0A2540;
            margin-bottom: 12px;
        }}
        .section-number {{
            color: #0A2540;
            margin-right: 8px;
        }}
        .section-content {{
            color: #425466;
            font-size: 10pt;
            line-height: 1.8;
        }}
        .section-content strong {{
            color: #0A2540;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .info-box {{
            background: #F8FAFC;
            padding: 18px;
            border-radius: 6px;
        }}
        .info-box h4 {{
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #64748B;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        .info-box p {{
            font-size: 10pt;
            color: #0A2540;
            margin-bottom: 4px;
        }}
        .pricing-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            background-color: white;
            page-break-inside: avoid;
        }}
        .pricing-table thead {{
            display: table-row-group;
        }}
        .pricing-table th,
        .pricing-table td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #E2E8F0;
            background: white !important;
            background-color: white !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        .pricing-table .table-header {{
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748B !important;
            font-weight: 600;
            border-bottom: 2px solid #E2E8F0;
            background: white !important;
            background-color: white !important;
        }}
        .pricing-table th {{
            background: white !important;
            background-color: white !important;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748B !important;
            font-weight: 600;
            border-bottom: 2px solid #E2E8F0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        .pricing-table td {{
            font-size: 10pt;
            color: #0A2540 !important;
            background: white !important;
            background-color: white !important;
        }}
        .pricing-table .total-row {{
            font-weight: 600;
        }}
        .pricing-table .total-row td {{
            border-bottom: none;
            border-top: 2px solid #e5e7eb;
            background: white !important;
            background-color: white !important;
            color: #0A2540 !important;
            font-size: 10pt;
        }}
        .pricing-table tr {{
            background: white !important;
            background-color: white !important;
        }}
        .bullet-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .bullet-list li {{
            padding: 6px 0;
            padding-left: 20px;
            position: relative;
            font-size: 10pt;
            color: #425466;
            line-height: 1.6;
        }}
        .bullet-list li:before {{
            content: "•";
            color: #0A2540;
            font-weight: bold;
            position: absolute;
            left: 0;
        }}
        .inclusions-exclusions {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}
        .inclusions-exclusions h4 {{
            font-size: 9pt;
            font-weight: 600;
            color: #0A2540;
            margin-bottom: 10px;
        }}
        .inclusions-exclusions ul {{
            list-style: none;
            padding: 0;
        }}
        .inclusions-exclusions li {{
            padding: 5px 0;
            padding-left: 20px;
            position: relative;
            font-size: 10pt;
            color: #425466;
        }}
        .inclusions li:before {{
            content: "✓";
            color: #10B981;
            position: absolute;
            left: 0;
            font-weight: 600;
        }}
        .exclusions li:before {{
            content: "✗";
            color: #EF4444;
            position: absolute;
            left: 0;
            font-weight: 600;
        }}
        .signatures {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 50px;
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid #E2E8F0;
            page-break-inside: avoid;
        }}
        .signature-box {{
            page-break-inside: avoid;
        }}
        .signature-box h4 {{
            font-size: 9pt;
            color: #64748B;
            margin-bottom: 12px;
            font-weight: 500;
        }}
        .signature-line {{
            height: 70px;
            border-bottom: 1px solid #0A2540;
            display: flex;
            align-items: flex-end;
            justify-content: flex-start;
            margin-bottom: 8px;
            padding-bottom: 8px;
            overflow: hidden;
        }}
        .signature-line img {{
            max-height: 100px;
            max-width: 280px;
            object-fit: contain;
            display: block;
        }}
        .signature-name {{
            font-size: 10pt;
            font-weight: 600;
            color: #0A2540;
        }}
        .signature-role {{
            font-size: 9pt;
            color: #64748B;
            font-weight: 400;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #E2E8F0;
            text-align: center;
            font-size: 8pt;
            color: #94A3B8;
        }}
        .terms-note {{
            font-size: 9pt;
            color: #64748B;
            font-style: italic;
            margin-top: 8px;
        }}

        /* Print-specific styles */
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            .pricing-table {{
                page-break-inside: avoid;
            }}
            .pricing-table th {{
                background: white !important;
                background-color: white !important;
                color: #64748B !important;
            }}
            .pricing-table td {{
                background: white !important;
                background-color: white !important;
                color: #0A2540 !important;
            }}
            .pricing-table .total-row td {{
                background: white !important;
                background-color: white !important;
            }}
        }}
    </style>
</head>
<body>
    <!-- Header with Logo on Top Right -->
    <div class="header">
        <div class="logo-section">
            {"<img src='" + logo_url + "' alt='Logo' class='logo'>" if logo_url else ""}
            {"" if logo_url else "<span class='company-name'>" + business_name + "</span>"}
        </div>
    </div>

    <!-- Contract Title -->
    <div class="contract-title">Service Agreement</div>

    <!-- Contract Intro -->
    <p class="contract-intro">
        This Service Agreement (the "Agreement") is made and entered into on <strong>{contract_date}</strong>
        by and between <strong>{business_name}</strong> ("Service Provider") and <strong>{client_name}</strong> ("Client").
        <br/><span style="color: #94A3B8; font-size: 9pt;">Contract #{contract_number}</span>
    </p>

    <!-- 1. Purpose -->
    <div class="section">
        <div class="section-title"><span class="section-number">1.</span>Purpose</div>
        <p class="section-content">
            The purpose of this Agreement is to outline the terms and conditions for the cleaning and maintenance services
            to be provided by <strong>{business_name}</strong> ("Service Provider") to <strong>{client_name}</strong> ("Client").
        </p>
    </div>

    <!-- 2. Scope of Work -->
    <div class="section">
        <div class="section-title"><span class="section-number">2.</span>Scope of Work</div>
        <p class="section-content" style="margin-bottom: 12px;">Service Provider will provide the following services to Client:</p>
        <div class="inclusions-exclusions">
            <div class="inclusions">
                <h4>Services Included</h4>
                <ul>{inclusions_html}</ul>
            </div>
            <div class="exclusions">
                <h4>Not Included</h4>
                <ul>{exclusions_html}</ul>
            </div>
        </div>
    </div>

    <!-- 3. Property & Service Details -->
    <div class="section">
        <div class="section-title"><span class="section-number">3.</span>Property & Service Details</div>
        <div class="info-grid">
            <div class="info-box">
                <h4>Service Location</h4>
                <p><strong>{client.business_name}</strong></p>
                <p>{client_address or "To be confirmed"}</p>
                <p>{client_email}</p>
                <p>{client_phone}</p>
            </div>
            <div class="info-box">
                <h4>Property Information</h4>
                <p><strong>Type:</strong> {property_type}</p>
                <p><strong>Size:</strong> {property_size} sq ft</p>
                <p><strong>Frequency:</strong> {frequency}</p>
                <p><strong>Start Date:</strong> {start_date}</p>
            </div>
        </div>
    </div>

    <!-- 4. Special Requests & Notes -->
    {"<div class='section'><div class='section-title'><span class='section-number'>4.</span>Special Requests & Client Notes</div><div class='info-box' style='background: #FEF3C7; border-left: 4px solid #F59E0B; margin-top: 12px;'><h4 style='color: #92400E; margin-bottom: 8px;'>⚠️ Important Client Requirements</h4><p style='color: #92400E; font-size: 10pt; line-height: 1.6; white-space: pre-wrap;'>" + special_requests + "</p></div></div>" if special_requests else ""}

    <!-- 5. Payment and Pricing -->
    <div class="section">
        <div class="section-title"><span class="section-number">5.</span>Payment and Pricing</div>
        <p class="section-content" style="margin-bottom: 12px;">
            The Client will pay the Service Provider the total agreed sum, outlined in the pricing below, for
            the completion of the scope of work outlined in this Agreement.
        </p>
        <table class="pricing-table">
            <tbody>
                <tr class="header-row">
                    <td class="table-header">Description</td>
                    <td class="table-header">Details</td>
                    <td class="table-header" style="text-align: right;">Amount (USD)</td>
                </tr>
                <tr>
                    <td>Base Service Rate</td>
                    <td>{frequency} cleaning service</td>
                    <td style="text-align: right;">{"Quote Pending" if quote.get('quote_pending') else f"USD ${quote['base_price']:,.2f}"}</td>
                </tr>
                {"<tr><td>Frequency Discount</td><td>" + str(quote['discount_percent']) + "% off for " + frequency.lower() + " service</td><td style='text-align: right; color: #10B981;'>-USD $" + f"{quote['discount_amount']:,.2f}" + "</td></tr>" if quote['discount_amount'] > 0 else ""}
                {"<tr><td>First Cleaning Discount</td><td>" + (f"${quote['first_cleaning_discount_value']:.2f} off" if quote.get('first_cleaning_discount_type') == 'fixed' else f"{quote['first_cleaning_discount_value']:.0f}% off") + " for first visit</td><td style='text-align: right; color: #10B981;'>-USD $" + f"{quote['first_cleaning_discount_amount']:,.2f}" + "</td></tr>" if quote.get('first_cleaning_discount_amount', 0) > 0 else ""}
                {"".join([f"<tr><td>{addon['name']}</td><td>{addon['quantity']} × ${addon['unit_price']:,.2f} {addon['pricing_metric']}</td><td style='text-align: right;'>USD ${addon['total_price']:,.2f}</td></tr>" for addon in quote.get('addon_details', [])]) if quote.get('addon_details') else ""}
                <tr class="total-row">
                    <td><strong>{"Total" if frequency in ["One-time", "One-time deep clean", "Per turnover", "On-demand", "As needed", "one-time"] else "Total Per Visit"}</strong></td>
                    <td>{"Service provider will provide quote" if quote.get('quote_pending') else f"Estimated {quote['estimated_hours']} hours, {quote['cleaners']} cleaner(s)"}</td>
                    <td style="text-align: right;"><strong>{"Quote Pending" if quote.get('quote_pending') else f"USD ${quote['final_price']:,.2f}"}</strong></td>
                </tr>
                {f"<tr><td style='padding-top: 20px;'><strong>Contract Term</strong></td><td style='padding-top: 20px;'>{quote['term_duration']} {quote['term_unit']} ({quote['service_occurrences']} visits)</td><td style='text-align: right; padding-top: 20px;'></td></tr><tr class='total-row'><td><strong>Total Contract Value</strong></td><td>For entire {quote['term_duration']} {quote['term_unit'].lower()} term</td><td style='text-align: right;'><strong>USD ${quote['total_term_rate']:,.2f}</strong></td></tr>" if quote.get('total_term_rate') and not quote.get('quote_pending') else ""}
            </tbody>
        </table>

        {f'''<div style="background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 6px; padding: 12px; margin-top: 16px; font-size: 9pt; color: #92400E;">
            <strong>⚠️ Time Estimate Disclaimer:</strong> The estimated {quote['estimated_hours']} hours is based on similar jobs for this service provider and property size. Actual cleaning time may be shorter or longer depending on specific conditions, level of cleaning required, and property layout. This estimate is provided for planning purposes only.
        </div>''' if not quote.get('quote_pending') else ""}

        <p class="terms-note">Payment due within {payment_due_days} days of service completion. A {late_fee}% late fee applies after due date.</p>
    </div>

    <!-- 6. Terms and Conditions -->
    <div class="section">
        <div class="section-title"><span class="section-number">6.</span>Terms and Conditions</div>
        <p class="section-content">
            This Agreement will begin on the date of acceptance and will remain in effect until all services have been completed.
        </p>

        <h4 style="margin-top: 16px; margin-bottom: 8px; color: #000000; font-size: 11pt;">Payment Terms</h4>
        <ul class="bullet-list">
            <li><strong>Payment Due:</strong> Payment is due within {payment_due_days} days of service completion</li>
            <li><strong>Late Fee:</strong> A {late_fee}% late fee will be applied to any balance not paid by the due date</li>
            <li><strong>Accepted Methods:</strong> Payment may be made via {accepted_methods}</li>
        </ul>

        <h4 style="margin-top: 16px; margin-bottom: 8px; color: #000000; font-size: 11pt;">Cancellation Policy</h4>
        <ul class="bullet-list">
            <li><strong>Notice Required:</strong> {cancellation_window}-hour advance notice is required for cancellations</li>
            <li><strong>Late Cancellation:</strong> Cancellations made with less than {cancellation_window} hours notice may be subject to a cancellation fee</li>
        </ul>

        <h4 style="margin-top: 16px; margin-bottom: 8px; color: #000000; font-size: 11pt;">General Terms</h4>
        <ul class="bullet-list">
            <li><strong>Access:</strong> Client agrees to provide necessary access to the property</li>
            <li><strong>Liability:</strong> Service provider maintains appropriate insurance coverage</li>
        </ul>
        <p class="terms-note">{'For recurring services, billing begins immediately upon signing, and the first cleaning will be scheduled separately based on your availability.' if is_recurring else 'For one-time services, the Service Start Date aligns with your scheduled service appointment.'}</p>
    </div>

    <!-- 7. Legal Provisions -->
    <div class="section">
        <div class="section-title"><span class="section-number">7.</span>Legal Provisions</div>
        <ul class="bullet-list">
            <li><strong>Governing Law:</strong> This Agreement shall be governed by the laws of the state in which the Service Provider operates.</li>
            <li><strong>Severability:</strong> If any provision is found invalid, the remaining provisions continue in full force.</li>
            <li><strong>Dispute Resolution:</strong> Parties agree to resolve disputes through good faith negotiation first.</li>
            <li><strong>Electronic Signatures:</strong> Electronic signatures are legally binding and have the same effect as handwritten signatures.</li>
        </ul>
    </div>

    <!-- Signatures -->
    <div class="signatures">
        <div class="signature-box">
            <h4>Service Provider</h4>
            <div class="signature-line">
                {provider_signature_html}
            </div>
            <div class="signature-name">{business_name}</div>
            <div class="signature-role">Authorized Representative</div>
        </div>
        <div class="signature-box">
            <h4>Client</h4>
            <div class="signature-line">
                {client_signature_html}
            </div>
            <div class="signature-name">{client_name}</div>
            <div class="signature-role">Client Representative</div>
        </div>
    </div>

    <!-- Footer -->
    <div class="footer">
        <p>Contract #{contract_number} • Generated on {contract_date}</p>
        <p style="margin-top: 4px;">All monetary amounts are in USD unless otherwise specified</p>
    </div>
</body>
</html>
"""
    return html

async def download_image_as_base64(url: str) -> str:
    """
    Download an image from a URL and return it as a base64 data URL.
    This is needed because Playwright cannot access external URLs during PDF generation.
    """
    import httpx
    import base64

    if not url:
        logger.warning("⚠️ download_image_as_base64 called with empty URL")
        return None

    try:
        logger.info(f"📥 Downloading image from: {url[:100]}...")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            logger.info(f"📥 Response status: {response.status_code}, content-type: {response.headers.get('content-type')}")
            response.raise_for_status()

            # Determine content type
            content_type = response.headers.get('content-type', 'image/png')

            # Handle content types that might have charset
            if ';' in content_type:
                content_type = content_type.split(';')[0].strip()

            # Convert to base64
            image_bytes = response.content
            if len(image_bytes) == 0:
                logger.warning("⚠️ Downloaded image has 0 bytes")
                return None
            b64_encoded = base64.b64encode(image_bytes).decode('utf-8')

            # Return as data URL
            return f"data:{content_type};base64,{b64_encoded}"
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP error downloading image: {e.response.status_code} - {e}")
        return None
    except httpx.RequestError as e:
        logger.error(f"❌ Request error downloading image: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to download image from {url[:100]}...: {type(e).__name__}: {e}")
        return None

async def html_to_pdf(html: str) -> bytes:
    """
    Convert HTML to PDF using Playwright via subprocess.
    Runs in a separate process to avoid asyncio conflicts on Windows.
    """
    import asyncio
    import base64
    import subprocess
    import sys
    import os

    # Get the path to the pdf_worker script
    worker_path = os.path.join(os.path.dirname(__file__), '..', 'pdf_worker.py')
    worker_path = os.path.abspath(worker_path)

    # Get the correct Python executable from the venv
    # sys.executable should point to the venv python when running from uvicorn
    python_exe = sys.executable

    # Encode HTML as base64 to safely pass via stdin
    html_b64 = base64.b64encode(html.encode('utf-8')).decode('utf-8')

    def run_worker():
        # Run the worker script as a separate process
        try:
            result = subprocess.run(
                [python_exe, worker_path],
                input=html_b64,
                capture_output=True,
                text=True,
                timeout=120,  # 120 second timeout for slow systems
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            if result.returncode != 0:
                raise Exception(f"PDF worker failed (exit {result.returncode}): {result.stderr}")

            # Decode the base64 PDF from stdout
            pdf_b64 = result.stdout.strip()
            if not pdf_b64:
                raise Exception("PDF worker returned empty output")
            return base64.b64decode(pdf_b64)
        except subprocess.TimeoutExpired:
            raise Exception("PDF generation timed out after 120 seconds")
        except Exception as e:
            raise Exception(f"PDF generation error: {str(e)}")

    # Run in thread pool to not block the event loop
    return await asyncio.to_thread(run_worker)

def upload_pdf_to_r2(pdf_bytes: bytes, owner_uid: str, contract_public_id: str) -> str:
    """Upload PDF to R2 and return the key"""
    key = f"contracts/{owner_uid}/{contract_public_id}.pdf"

    r2 = get_r2_client()
    r2.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    return key

@router.post("/generate-pdf")
async def generate_contract_pdf(
    data: ContractGenerateRequest,
    db: Session = Depends(get_db)
):
    """Generate a PDF contract for a client submission and store in R2"""
    try:
        # Get the business owner
        user = db.query(User).filter(User.firebase_uid == data.ownerUid).first()
        if not user:
            raise HTTPException(status_code=404, detail="Business not found")

        # Get business config
        config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Business configuration not found")

        # Get client
        client = db.query(Client).filter(Client.id == data.clientId).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Calculate quote
        quote = calculate_quote(config, data.formData)

        # Create contract record first to get public_id for secure contract numbering
        contract = Contract(
            user_id=user.id,
            client_id=client.id,
            title=f"Service Agreement - {client.business_name}",
            description=f"Auto-generated contract for {quote['frequency']} cleaning service",
            contract_type="recurring" if quote['frequency'] not in ["One-time", "One-time deep clean", "Per turnover", "On-demand", "As needed", "one-time"] else "one-time",
            status="new",
            total_value=quote['final_price'],
            payment_terms=f"Net {config.payment_due_days or 15} days",
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # Generate HTML with contract public_id for secure contract numbering
        html = await generate_contract_html(
            config,
            client,
            data.formData,
            quote,
            db,
            client_signature=data.clientSignature,
            contract_public_id=contract.public_id
        )

        # Generate PDF
        pdf_bytes = await html_to_pdf(html)

        # Upload PDF to R2 and store the key
        pdf_key = upload_pdf_to_r2(pdf_bytes, data.ownerUid, contract.public_id)
        contract.pdf_key = pdf_key
        db.commit()

        # Generate backend URL instead of presigned R2 URL to avoid CORS issues
        from ..config import FRONTEND_URL
        # Determine the backend base URL based on the frontend URL
        if "localhost" in FRONTEND_URL:
            backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace("localhost:5174", "localhost:8000")
        else:
            backend_base = "https://api.cleanenroll.com"

        backend_pdf_url = f"{backend_base}/contracts/pdf/public/{contract.public_id}"
        return {
            "contractId": contract.id,
            "pdfKey": pdf_key,
            "pdfUrl": backend_pdf_url,
            "message": "Contract generated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating contract PDF: {str(e)}", exc_info=True)
        # Don't expose technical details to users in production
        raise HTTPException(status_code=500, detail="Failed to generate contract. Please try again or contact support.")

@router.get("/pdf/{contract_id}")
async def get_contract_pdf(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a backend URL for a contract PDF (avoids CORS issues)"""
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.pdf_key:
        raise HTTPException(status_code=404, detail="No PDF available for this contract")

    try:
        # Generate backend URL instead of presigned R2 URL to avoid CORS issues
        from ..config import FRONTEND_URL
        # Determine the backend base URL based on the frontend URL
        if "localhost" in FRONTEND_URL:
            backend_base = FRONTEND_URL.replace("localhost:5173", "localhost:8000").replace("localhost:5174", "localhost:8000")
        else:
            backend_base = "https://api.cleanenroll.com"

        backend_pdf_url = f"{backend_base}/contracts/pdf/public/{contract.public_id}"

        return {
            "url": backend_pdf_url,
            "contractId": contract.id,
            "title": contract.title
        }
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF URL")

@router.get("/pdf/download/{contract_id}")
async def download_contract_pdf(
    contract_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _ip: None = Depends(rate_limit_download_per_ip)
):
    """
    Download a contract PDF directly
    Rate limited: 5 downloads per minute per IP, 3 downloads per minute per contract
    """
    # Apply per-contract rate limit
    await rate_limit_per_contract(request, contract_id)
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.pdf_key:
        raise HTTPException(status_code=404, detail="No PDF available for this contract")

    try:
        r2 = get_r2_client()
        response = r2.get_object(Bucket=R2_BUCKET_NAME, Key=contract.pdf_key)
        pdf_bytes = response['Body'].read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=contract-{contract.id}.pdf",
                "Access-Control-Allow-Origin": FRONTEND_URL,
                "Access-Control-Allow-Methods": "GET",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to download PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download PDF")

@router.get("/pdf/public/{contract_public_id}")
async def view_contract_pdf_public(
    contract_public_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _ip: None = Depends(rate_limit_download_per_ip)
):
    """
    View a contract PDF publicly using the contract's public ID
    Rate limited: 5 downloads per minute per IP, 3 downloads per minute per contract
    """
    # Validate UUID format
    from .contracts import validate_uuid
    if not validate_uuid(contract_public_id):
        raise HTTPException(status_code=400, detail="Invalid contract ID format")

    contract = db.query(Contract).filter(Contract.public_id == contract_public_id).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if not contract.pdf_key:
        raise HTTPException(status_code=404, detail="No PDF available for this contract")

    # Apply per-contract rate limit
    await rate_limit_per_contract(request, contract.id)

    try:
        r2 = get_r2_client()
        response = r2.get_object(Bucket=R2_BUCKET_NAME, Key=contract.pdf_key)
        pdf_bytes = response['Body'].read()

        headers = {
            "Content-Disposition": f"inline; filename=contract-{contract.id}.pdf",
            "Access-Control-Allow-Origin": FRONTEND_URL,
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Cache-Control": "no-cache, must-revalidate",
        }
        if contract.pdf_hash:
            headers["ETag"] = contract.pdf_hash

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers=headers
        )
    except Exception as e:
        logger.error(f"❌ Failed to serve PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load PDF")

@router.get("/preview/{client_id}")
async def preview_contract(
    client_id: int,
    owner_uid: str,
    db: Session = Depends(get_db)
):
    """Preview contract HTML (for debugging)"""
    user = db.query(User).filter(User.firebase_uid == owner_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")

    config = db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Business configuration not found")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get form data from client
    form_data = client.form_data if client.form_data else {}

    quote = calculate_quote(config, form_data)
    html = await generate_contract_html(config, client, form_data, quote, db)

    return Response(content=html, media_type="text/html")
