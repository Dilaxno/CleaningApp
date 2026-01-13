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
from ..config import R2_BUCKET_NAME
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


def calculate_quote(config: BusinessConfig, form_data: dict) -> dict:
    """Calculate quote based on business config and form data"""
    import logging
    logger = logging.getLogger(__name__)
    
    pricing_model = config.pricing_model
    property_size = int(form_data.get("squareFootage", 0) or 0)
    num_rooms = int(form_data.get("numberOfOffices", 0) or form_data.get("numberOfRooms", 0) or 0)
    frequency = form_data.get("cleaningFrequency", "Weekly")
    
    logger.info(f"📊 Quote calculation - pricing_model: {pricing_model}, property_size: {property_size}, num_rooms: {num_rooms}, frequency: {frequency}")
    logger.info(f"📊 Config rates - sqft: {config.rate_per_sqft}, room: {config.rate_per_room}, hourly: {config.hourly_rate}, flat: {config.flat_rate}")
    
    base_price = 0.0
    estimated_hours = 0.0
    
    # Calculate base price based on pricing model
    if pricing_model == "sqft" and config.rate_per_sqft:
        base_price = property_size * config.rate_per_sqft
        # Estimate time: cleaning_time_per_sqft is minutes per 1000 sqft
        if config.cleaning_time_per_sqft:
            estimated_hours = (property_size / 1000) * (config.cleaning_time_per_sqft / 60)
        elif property_size > 0:
            # Default: ~2 hours per 1000 sqft
            estimated_hours = max(1, property_size / 500)
    elif pricing_model == "room" and config.rate_per_room:
        base_price = num_rooms * config.rate_per_room
        # Estimate ~30 min per room, or estimate from property size if no rooms specified
        if num_rooms > 0:
            estimated_hours = num_rooms * 0.5
        elif property_size > 0:
            # Fallback: estimate rooms from size (~200 sqft per room) then calculate hours
            estimated_rooms = max(1, property_size / 200)
            estimated_hours = estimated_rooms * 0.5
        else:
            estimated_hours = 2  # Default minimum
    elif pricing_model == "hourly" and config.hourly_rate:
        # Estimate hours based on size
        if config.cleaning_time_per_sqft and property_size:
            estimated_hours = (property_size / 1000) * (config.cleaning_time_per_sqft / 60)
        else:
            estimated_hours = max(2, property_size / 500)  # Default estimate
        base_price = estimated_hours * config.hourly_rate
    elif pricing_model == "flat" and config.flat_rate:
        base_price = config.flat_rate
        estimated_hours = 2  # Default estimate for flat rate
    
    # If no pricing model matched or base_price is still 0, try fallbacks
    if base_price == 0:
        logger.warning(f"⚠️ Base price is 0 - trying fallback rates")
        # Try each rate type as fallback
        if config.flat_rate and config.flat_rate > 0:
            base_price = config.flat_rate
            estimated_hours = 2
            logger.info(f"📊 Using flat_rate fallback: ${base_price}")
        elif config.hourly_rate and config.hourly_rate > 0:
            estimated_hours = max(2, property_size / 500) if property_size > 0 else 2
            base_price = estimated_hours * config.hourly_rate
            logger.info(f"📊 Using hourly_rate fallback: ${base_price}")
        elif config.rate_per_sqft and config.rate_per_sqft > 0 and property_size > 0:
            base_price = property_size * config.rate_per_sqft
            estimated_hours = max(1, property_size / 500)
            logger.info(f"📊 Using rate_per_sqft fallback: ${base_price}")
        elif config.rate_per_room and config.rate_per_room > 0:
            # Estimate rooms from property size if not provided
            rooms = num_rooms if num_rooms > 0 else max(1, property_size / 200) if property_size > 0 else 5
            base_price = rooms * config.rate_per_room
            estimated_hours = rooms * 0.5
            logger.info(f"📊 Using rate_per_room fallback: ${base_price}")
    
    # Apply minimum charge
    if config.minimum_charge and base_price < config.minimum_charge:
        base_price = config.minimum_charge
        logger.info(f"📊 Applied minimum charge: ${base_price}")
    
    # Apply frequency discount
    discount_percent = 0
    if frequency == "Weekly" and config.discount_weekly:
        discount_percent = config.discount_weekly
    elif frequency == "Bi-weekly" and config.discount_monthly:
        discount_percent = config.discount_monthly
    elif frequency == "Monthly" and config.discount_long_term:
        discount_percent = config.discount_long_term
    
    discount_amount = base_price * (discount_percent / 100) if discount_percent else 0
    final_price = base_price - discount_amount
    
    # Determine number of cleaners
    cleaners = config.cleaners_small_job or 1
    if property_size > 2000:
        cleaners = config.cleaners_large_job or 2
    
    # Calculate term duration total if provided (for recurring services)
    term_duration = form_data.get("contractTermDuration")
    term_unit = form_data.get("contractTermUnit", "Months")
    total_term_rate = None
    service_occurrences = None
    
    if term_duration and frequency != "One-time":
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
    
    logger.info(f"📊 Final quote - base: ${base_price}, discount: ${discount_amount}, final: ${final_price}, hours: {estimated_hours}, pending: {quote_pending}")
    
    return {
        "base_price": round(base_price, 2),
        "discount_percent": discount_percent,
        "discount_amount": round(discount_amount, 2),
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
    }


async def generate_contract_html(
    business_config: BusinessConfig,
    client: Client,
    form_data: dict,
    quote: dict,
    client_signature: Optional[str] = None,
    provider_signature: Optional[str] = None
) -> str:
    """Generate HTML for the contract"""
    
    # Debug logging for business config pricing
    logger.info(f"💰 Business config pricing - model: {business_config.pricing_model}, sqft: {business_config.rate_per_sqft}, room: {business_config.rate_per_room}, hourly: {business_config.hourly_rate}, flat: {business_config.flat_rate}")
    logger.info(f"🖼️ Business config branding - name: {business_config.business_name}, logo: {business_config.logo_url}")
    
    # Warn if all pricing fields are NULL
    if not any([business_config.rate_per_sqft, business_config.rate_per_room, business_config.hourly_rate, business_config.flat_rate]):
        logger.warning(f"⚠️ ALL PRICING FIELDS ARE NULL for user_id: {business_config.user_id} - user needs to update pricing in Settings")
    
    # Debug logging for signatures
    logger.info(f"🖊️ Generating PDF - Client signature present: {bool(client_signature)}, Provider signature present: {bool(provider_signature)}")
    if client_signature:
        logger.info(f"📝 Client signature format: {client_signature[:50]}..." if len(client_signature) > 50 else f"📝 Client signature: {client_signature}")
    
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
                logger.info(f"ℹ️ Logo URL is already a full URL")
            else:
                presigned_logo_url = generate_presigned_url(business_config.logo_url)
            logger.info(f"✅ Generated presigned URL for logo: {presigned_logo_url[:100]}...")
            logo_url = await download_image_as_base64(presigned_logo_url)
            if logo_url:
                logger.info(f"✅ Logo downloaded and converted to base64 ({len(logo_url)} chars)")
            else:
                logger.warning(f"⚠️ Logo download returned None for URL: {presigned_logo_url[:100]}...")
        except Exception as e:
            logger.error(f"❌ Failed to generate/download logo: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    else:
        logger.info("ℹ️ No logo_url configured in business config")
    
    # Download and convert provider signature to base64
    if provider_signature:
        # Check if it's already base64 or a URL
        if provider_signature.startswith("data:image"):
            signature_url = provider_signature
        elif provider_signature.startswith("http"):
            signature_url = await download_image_as_base64(provider_signature)
            if signature_url:
                logger.info("✅ Provider signature downloaded and converted to base64")
        else:
            signature_url = provider_signature
    elif business_config.signature_url:
        try:
            presigned_sig_url = generate_presigned_url(business_config.signature_url)
            logger.info(f"✅ Generated presigned URL for signature: {business_config.signature_url}")
            signature_url = await download_image_as_base64(presigned_sig_url)
            if signature_url:
                logger.info("✅ Provider signature downloaded and converted to base64")
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate signature URL: {e}")
    
    # Download and convert client signature to base64
    if client_signature:
        if client_signature.startswith("data:image"):
            # Already base64, use as-is
            pass
        elif client_signature.startswith("http"):
            # Download from URL
            client_signature_b64 = await download_image_as_base64(client_signature)
            if client_signature_b64:
                client_signature = client_signature_b64
                logger.info("✅ Client signature downloaded and converted to base64")
        # else: assume it's already in correct format
    
    # Contract details
    contract_date = datetime.now().strftime("%B %d, %Y")
    contract_number = f"CLN-{datetime.now().strftime('%Y%m%d')}-{client.id:04d}"
    
    # Smart start date logic based on service type
    frequency = quote["frequency"]
    is_recurring = frequency not in ["One-time", "one-time"]
    
    if is_recurring:
        # Recurring contracts: billing starts on signing date
        start_date = datetime.now().strftime("%B %d, %Y")
        start_date_note = "Agreement effective immediately upon signing. First service will be scheduled separately."
    else:
        # One-time/deep cleans: align with service date (typically 7 days out)
        start_date = (datetime.now() + timedelta(days=7)).strftime("%B %d, %Y")
        start_date_note = "Agreement effective on scheduled service date."
    
    payment_due_days = business_config.payment_due_days or 15
    late_fee = business_config.late_fee_percent or 1.5
    
    # Client info
    client_name = client.contact_name or client.business_name
    client_email = client.email or ""
    client_phone = client.phone or ""
    client_address = form_data.get("billingAddress", "") or form_data.get("address", "")
    
    # Property details
    property_size = form_data.get("squareFootage", "N/A")
    property_type = client.property_type or "Commercial"
    
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
        }}
        .pricing-table th,
        .pricing-table td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #E2E8F0;
        }}
        .pricing-table th {{
            background: #F8FAFC;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748B;
            font-weight: 500;
        }}
        .pricing-table td {{
            font-size: 10pt;
            color: #0A2540;
        }}
        .pricing-table .total-row {{
            background: #0A2540;
            font-weight: 600;
        }}
        .pricing-table .total-row td {{
            border-bottom: none;
            border-top: 2px solid #e5e7eb;
            color: #FFFFFF;
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
            max-height: 60px;
            max-width: 180px;
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

    <!-- 4. Payment and Pricing -->
    <div class="section">
        <div class="section-title"><span class="section-number">4.</span>Payment and Pricing</div>
        <p class="section-content" style="margin-bottom: 12px;">
            The Client will pay the Service Provider the total agreed sum, outlined in the pricing below, for 
            the completion of the scope of work outlined in this Agreement.
        </p>
        <table class="pricing-table">
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Details</th>
                    <th style="text-align: right;">Amount (USD)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Base Service Rate</td>
                    <td>{frequency} cleaning service</td>
                    <td style="text-align: right;">{"Quote Pending" if quote.get('quote_pending') else f"USD ${quote['base_price']:,.2f}"}</td>
                </tr>
                {"<tr><td>Frequency Discount</td><td>" + str(quote['discount_percent']) + "% off for " + frequency.lower() + " service</td><td style='text-align: right; color: #10B981;'>-USD $" + f"{quote['discount_amount']:,.2f}" + "</td></tr>" if quote['discount_amount'] > 0 else ""}
                <tr class="total-row">
                    <td><strong>{"Total" if frequency in ["One-time", "one-time"] else "Total Per Visit"}</strong></td>
                    <td>{"Service provider will provide quote" if quote.get('quote_pending') else f"Estimated {quote['estimated_hours']} hours, {quote['cleaners']} cleaner(s)"}</td>
                    <td style="text-align: right;"><strong>{"Quote Pending" if quote.get('quote_pending') else f"USD ${quote['final_price']:,.2f}"}</strong></td>
                </tr>
                {f"<tr><td colspan='3' style='padding-top: 15px; border-top: 2px solid #e5e7eb;'></td></tr><tr style='background-color: #f8fafc;'><td><strong>Contract Term</strong></td><td>{quote['term_duration']} {quote['term_unit']} ({quote['service_occurrences']} visits)</td><td style='text-align: right;'></td></tr><tr class='total-row'><td><strong>Total Contract Value</strong></td><td>For entire {quote['term_duration']} {quote['term_unit'].lower()} term</td><td style='text-align: right;'><strong>USD ${quote['total_term_rate']:,.2f}</strong></td></tr>" if quote.get('total_term_rate') and not quote.get('quote_pending') else ""}
            </tbody>
        </table>
        <p class="terms-note">Payment due within {payment_due_days} days of service completion. A {late_fee}% late fee applies after due date.</p>
    </div>

    <!-- 5. Terms -->
    <div class="section">
        <div class="section-title"><span class="section-number">5.</span>Terms</div>
        <p class="section-content">
            This Agreement will begin on the date of acceptance and will remain in effect until all services have been completed.
        </p>
        <ul class="bullet-list" style="margin-top: 12px;">
            <li><strong>Cancellation:</strong> 24-hour notice required for cancellations to avoid charges</li>
            <li><strong>Access:</strong> Client agrees to provide necessary access to the property</li>
            <li><strong>Liability:</strong> Service provider maintains appropriate insurance coverage</li>
        </ul>
        <p class="terms-note">{'For recurring services, billing begins immediately upon signing, and the first cleaning will be scheduled separately based on your availability.' if is_recurring else 'For one-time services, the Service Start Date aligns with your scheduled service appointment.'}</p>
    </div>

    <!-- 6. Legal Provisions -->
    <div class="section">
        <div class="section-title"><span class="section-number">6.</span>Legal Provisions</div>
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
                {"<img src='" + signature_url + "' alt='Provider Signature'>" if signature_url else ""}
            </div>
            <div class="signature-name">{business_name}</div>
            <div class="signature-role">Authorized Representative</div>
        </div>
        <div class="signature-box">
            <h4>Client</h4>
            <div class="signature-line">
                {"<img src='" + client_signature + "' alt='Client Signature'>" if client_signature else ""}
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
                
            logger.info(f"📥 Downloaded {len(image_bytes)} bytes")
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


def upload_pdf_to_r2(pdf_bytes: bytes, owner_uid: str, contract_id: int) -> str:
    """Upload PDF to R2 and return the key"""
    key = f"contracts/{owner_uid}/{contract_id}-{uuid.uuid4()}.pdf"
    
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
    logger.info(f"📄 Generating contract PDF for client_id: {data.clientId}")
    
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
        
        # Generate HTML
        html = await generate_contract_html(
            config, 
            client, 
            data.formData, 
            quote,
            client_signature=data.clientSignature
        )
        
        # Generate PDF
        pdf_bytes = await html_to_pdf(html)
        
        # Create contract record first to get the ID
        contract = Contract(
            user_id=user.id,
            client_id=client.id,
            title=f"Service Agreement - {client.business_name}",
            description=f"Auto-generated contract for {quote['frequency']} cleaning service",
            contract_type="recurring" if quote['frequency'] != "One-time" else "one-time",
            status="new",
            total_value=quote['final_price'],
            payment_terms=f"Net {config.payment_due_days or 15} days",
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)
        
        # Upload PDF to R2 and store the key
        pdf_key = upload_pdf_to_r2(pdf_bytes, data.ownerUid, contract.id)
        contract.pdf_key = pdf_key
        db.commit()
        
        # Generate presigned URL for immediate access
        presigned_url = generate_presigned_url(pdf_key, expiration=3600)
        
        logger.info(f"✅ Contract PDF generated and stored, contract_id: {contract.id}, key: {pdf_key}")
        
        return {
            "contractId": contract.id,
            "pdfKey": pdf_key,
            "pdfUrl": presigned_url,
            "message": "Contract generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating contract PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf/{contract_id}")
async def get_contract_pdf(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a presigned URL for a contract PDF"""
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.user_id == current_user.id
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if not contract.pdf_key:
        raise HTTPException(status_code=404, detail="No PDF available for this contract")
    
    try:
        presigned_url = generate_presigned_url(contract.pdf_key, expiration=3600)
        return {
            "url": presigned_url,
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
                "Content-Disposition": f"attachment; filename=contract-{contract.id}.pdf"
            }
        )
    except Exception as e:
        logger.error(f"❌ Failed to download PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download PDF")


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
    html = await generate_contract_html(config, client, form_data, quote)
    
    return Response(content=html, media_type="text/html")
