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
    pricing_model = config.pricing_model
    property_size = int(form_data.get("squareFootage", 0) or 0)
    num_rooms = int(form_data.get("numberOfOffices", 0) or form_data.get("numberOfRooms", 0) or 0)
    frequency = form_data.get("cleaningFrequency", "Weekly")
    
    base_price = 0.0
    estimated_hours = 0.0
    
    # Calculate base price based on pricing model
    if pricing_model == "sqft" and config.rate_per_sqft:
        base_price = property_size * config.rate_per_sqft
        # Estimate time: cleaning_time_per_sqft is minutes per 1000 sqft
        if config.cleaning_time_per_sqft:
            estimated_hours = (property_size / 1000) * (config.cleaning_time_per_sqft / 60)
    elif pricing_model == "room" and config.rate_per_room:
        base_price = num_rooms * config.rate_per_room
        # Estimate ~30 min per room
        estimated_hours = num_rooms * 0.5
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
    
    # Apply minimum charge
    if config.minimum_charge and base_price < config.minimum_charge:
        base_price = config.minimum_charge
    
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
    
    # Debug logging for signatures
    logger.info(f"🖊️ Generating PDF - Client signature present: {bool(client_signature)}, Provider signature present: {bool(provider_signature)}")
    if client_signature:
        logger.info(f"📝 Client signature format: {client_signature[:50]}..." if len(client_signature) > 50 else f"📝 Client signature: {client_signature}")
    
    # Get branding
    business_name = business_config.business_name or "Cleaning Service"
    logo_url = None
    signature_url = None
    
    # Download and convert logo to base64 for Playwright
    if business_config.logo_url:
        try:
            presigned_logo_url = generate_presigned_url(business_config.logo_url)
            logger.info(f"✅ Generated presigned URL for logo: {business_config.logo_url}")
            logo_url = await download_image_as_base64(presigned_logo_url)
            if logo_url:
                logger.info("✅ Logo downloaded and converted to base64")
        except Exception as e:
            logger.warning(f"⚠️ Failed to generate logo URL: {e}")
    
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
    inclusions = business_config.standard_inclusions or []
    exclusions = business_config.standard_exclusions or []
    
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
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #1E293B;
            background: white;
            padding: 40px 50px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #000000;
        }}
        .logo-section {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .logo {{
            max-height: 60px;
            max-width: 180px;
            object-fit: contain;
        }}
        .company-name {{
            font-size: 24pt;
            font-weight: 700;
            color: #1E293B;
        }}
        .contract-info {{
            text-align: right;
        }}
        .contract-title {{
            font-size: 14pt;
            font-weight: 600;
            color: #000000;
            margin-bottom: 5px;
        }}
        .contract-number {{
            font-size: 10pt;
            color: #64748B;
        }}
        .contract-date {{
            font-size: 10pt;
            color: #64748B;
        }}
        h1 {{
            font-size: 20pt;
            color: #1E293B;
            text-align: center;
            margin: 30px 0;
            padding-bottom: 15px;
            border-bottom: 1px solid #E2E8F0;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        .section-title {{
            font-size: 12pt;
            font-weight: 600;
            color: #000000;
            margin-bottom: 12px;
            padding-bottom: 5px;
            border-bottom: 1px solid #E2E8F0;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .info-box {{
            background: #F8FAFC;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
        }}
        .info-box h4 {{
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748B;
            margin-bottom: 8px;
        }}
        .info-box p {{
            font-size: 10pt;
            color: #1E293B;
            margin-bottom: 4px;
        }}
        .pricing-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .pricing-table th,
        .pricing-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #E2E8F0;
        }}
        .pricing-table th {{
            background: #F8FAFC;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748B;
            font-weight: 600;
        }}
        .pricing-table td {{
            font-size: 10pt;
        }}
        .pricing-table .total-row {{
            background: #000000;
            color: white;
            font-weight: 600;
        }}
        .pricing-table .total-row td {{
            border-bottom: none;
        }}
        .terms-list {{
            list-style: none;
            padding: 0;
        }}
        .terms-list li {{
            padding: 8px 0;
            padding-left: 20px;
            position: relative;
            font-size: 10pt;
        }}
        .terms-list li:before {{
            content: "•";
            color: #000000;
            font-weight: bold;
            position: absolute;
            left: 0;
        }}
        .inclusions-exclusions {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .inclusions-exclusions ul {{
            list-style: none;
            padding: 0;
        }}
        .inclusions-exclusions li {{
            padding: 5px 0;
            padding-left: 18px;
            position: relative;
            font-size: 10pt;
        }}
        .inclusions li:before {{
            content: "✓";
            color: #000000;
            position: absolute;
            left: 0;
        }}
        .exclusions li:before {{
            content: "✗";
            color: #000000;
            position: absolute;
            left: 0;
        }}
        .signatures {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            margin-top: 40px;
            padding-top: 30px;
            border-top: 2px solid #E2E8F0;
        }}
        .signature-box {{
            text-align: center;
        }}
        .signature-box h4 {{
            font-size: 10pt;
            color: #64748B;
            margin-bottom: 10px;
        }}
        .signature-line {{
            height: 80px;
            border: 2px dashed #E2E8F0;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 10px;
            background: #FAFAFA;
        }}
        .signature-line img {{
            max-height: 70px;
            max-width: 200px;
            object-fit: contain;
        }}
        .signature-name {{
            font-size: 10pt;
            font-weight: 600;
            color: #1E293B;
        }}
        .signature-role {{
            font-size: 9pt;
            color: #64748B;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #E2E8F0;
            text-align: center;
            font-size: 9pt;
            color: #64748B;
        }}
        .highlight {{
            background: #000000;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="logo-section">
            {"<img src='" + logo_url + "' alt='Logo' class='logo'>" if logo_url else ""}
            <span class="company-name">{business_name}</span>
        </div>
        <div class="contract-info">
            <div class="contract-title">SERVICE AGREEMENT</div>
            <div class="contract-number">{contract_number}</div>
            <div class="contract-date">{contract_date}</div>
        </div>
    </div>

    <!-- Parties Section -->
    <div class="section">
        <div class="section-title">Parties to This Agreement</div>
        <div class="info-grid">
            <div class="info-box">
                <h4>Service Provider</h4>
                <p><strong>{business_name}</strong></p>
                <p>Professional Cleaning Services</p>
            </div>
            <div class="info-box">
                <h4>Client</h4>
                <p><strong>{client_name}</strong></p>
                <p>{client.business_name}</p>
                <p>{client_email}</p>
                <p>{client_phone}</p>
            </div>
        </div>
    </div>

    <!-- Property Details -->
    <div class="section">
        <div class="section-title">Property Details</div>
        <div class="info-grid">
            <div class="info-box">
                <h4>Service Location</h4>
                <p>{client_address or "To be confirmed"}</p>
            </div>
            <div class="info-box">
                <h4>Property Information</h4>
                <p><strong>Type:</strong> {property_type}</p>
                <p><strong>Size:</strong> {property_size} sq ft</p>
                <p><strong>Frequency:</strong> {frequency}</p>
            </div>
        </div>
    </div>

    <!-- Pricing -->
    <div class="section">
        <div class="section-title">Service Pricing</div>
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
                    <td style="text-align: right;">USD ${quote['base_price']:,.2f}</td>
                </tr>
                {"<tr><td>Frequency Discount</td><td>" + str(quote['discount_percent']) + "% off for " + frequency.lower() + " service</td><td style='text-align: right; color: #000000;'>-USD $" + f"{quote['discount_amount']:,.2f}" + "</td></tr>" if quote['discount_amount'] > 0 else ""}
                <tr class="total-row">
                    <td><strong>Total Per Visit</strong></td>
                    <td>Estimated {quote['estimated_hours']} hours, {quote['cleaners']} cleaner(s)</td>
                    <td style="text-align: right;"><strong>USD ${quote['final_price']:,.2f}</strong></td>
                </tr>
                {f"<tr><td colspan='3' style='padding-top: 15px; border-top: 2px solid #e5e7eb;'></td></tr><tr style='background-color: #f8fafc;'><td><strong>Contract Term</strong></td><td>{quote['term_duration']} {quote['term_unit']} ({quote['service_occurrences']} visits)</td><td style='text-align: right;'></td></tr><tr class='total-row' style='background-color: #00C4B4; color: white;'><td><strong>Total Contract Value</strong></td><td>For entire {quote['term_duration']} {quote['term_unit'].lower()} term</td><td style='text-align: right;'><strong>USD ${quote['total_term_rate']:,.2f}</strong></td></tr>" if quote.get('total_term_rate') else ""}
            </tbody>
        </table>
    </div>

    <!-- Services Included/Excluded -->
    <div class="section">
        <div class="section-title">Scope of Services</div>
        <div class="inclusions-exclusions">
            <div class="inclusions">
                <h4 style="font-size: 10pt; color: #000000; margin-bottom: 10px;">✓ Services Included</h4>
                <ul>{inclusions_html}</ul>
            </div>
            <div class="exclusions">
                <h4 style="font-size: 10pt; color: #000000; margin-bottom: 10px;">✗ Not Included</h4>
                <ul>{exclusions_html}</ul>
            </div>
        </div>
    </div>

    <!-- Terms -->
    <div class="section">
        <div class="section-title">Terms & Conditions</div>
        <ul class="terms-list">
            <li><strong>Service Start Date:</strong> {start_date}<br/>
                <span style="font-size: 8pt; color: #64748B; font-style: italic;">{start_date_note}</span>
            </li>
            <li><strong>Payment Terms:</strong> Payment due within {payment_due_days} days of service completion. All amounts are in USD.</li>
            <li><strong>Late Payment:</strong> {late_fee}% late fee applies after due date</li>
            <li><strong>Cancellation:</strong> 24-hour notice required for cancellations to avoid charges</li>
            <li><strong>Access:</strong> Client agrees to provide necessary access to the property</li>
            <li><strong>Liability:</strong> Service provider maintains appropriate insurance coverage</li>
        </ul>
        <p style="margin-top: 15px; font-size: 9pt; color: #64748B; line-height: 1.6;">
            <strong>Note on Service Start Date:</strong> The Service Start Date activates the agreement terms and conditions. {'For recurring services, billing begins immediately upon signing, and the first cleaning will be scheduled separately based on your availability.' if is_recurring else 'For one-time services, the Service Start Date aligns with your scheduled service appointment.'}
        </p>
    </div>

    <!-- Legal Clauses -->
    <div class="section">
        <div class="section-title">Legal Provisions</div>
        <div style="font-size: 9pt; color: #475569; line-height: 1.7;">
            <p style="margin-bottom: 12px;"><strong>1. Governing Law & Jurisdiction:</strong> This Agreement shall be governed by and construed in accordance with the laws of the state in which the Service Provider operates. Any disputes arising under this Agreement shall be resolved in the courts of competent jurisdiction in that state.</p>
            
            <p style="margin-bottom: 12px;"><strong>2. Severability:</strong> If any provision of this Agreement is found to be invalid, illegal, or unenforceable, the remaining provisions shall continue in full force and effect. The invalid provision shall be modified to the minimum extent necessary to make it valid and enforceable.</p>
            
            <p style="margin-bottom: 12px;"><strong>3. Non-Waiver:</strong> The failure of either party to enforce any provision of this Agreement shall not constitute a waiver of that party's right to enforce that provision or any other provision in the future.</p>
            
            <p style="margin-bottom: 12px;"><strong>4. Dispute Resolution:</strong> The parties agree to attempt to resolve any disputes arising from this Agreement through good faith negotiation. If negotiation fails, disputes shall be resolved through binding arbitration in accordance with the rules of the American Arbitration Association, unless both parties agree to court proceedings.</p>
            
            <p style="margin-bottom: 12px;"><strong>5. Entire Agreement:</strong> This Agreement constitutes the entire agreement between the parties and supersedes all prior negotiations, representations, or agreements relating to this subject matter.</p>
            
            <p><strong>6. Electronic Signatures:</strong> Both parties agree that electronic signatures on this Agreement are legally binding and have the same legal effect as handwritten signatures.</p>
        </div>
    </div>

    <!-- Signatures -->
    <div class="signatures">
        <div class="signature-box">
            <h4>Service Provider</h4>
            <div class="signature-line">
                {"<img src='" + signature_url + "' alt='Provider Signature'>" if signature_url else "<span style='color: #94A3B8; font-size: 9pt;'>Signature pending</span>"}
            </div>
            <div class="signature-name">{business_name}</div>
            <div class="signature-role">Authorized Representative</div>
        </div>
        <div class="signature-box">
            <h4>Client</h4>
            <div class="signature-line">
                {"<img src='" + client_signature + "' alt='Client Signature' style='max-width: 200px; max-height: 80px;'>" if client_signature else "<span style='color: #94A3B8; font-size: 9pt;'>Awaiting signature</span>"}
            </div>
            <div class="signature-name">{client_name}</div>
            <div class="signature-role">Client Representative</div>
        </div>
    </div>

    <!-- Footer -->
    <div class="footer">
        <p style="margin-bottom: 4px;">Electronically generated via CleanEnroll</p>
        <p style="margin-bottom: 4px;">Contract #{contract_number} • Generated on {contract_date}</p>
        <p style="font-size: 8pt; color: #94A3B8;">All monetary amounts are in USD unless otherwise specified</p>
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
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Determine content type
            content_type = response.headers.get('content-type', 'image/png')
            
            # Convert to base64
            image_bytes = response.content
            b64_encoded = base64.b64encode(image_bytes).decode('utf-8')
            
            # Return as data URL
            return f"data:{content_type};base64,{b64_encoded}"
    except Exception as e:
        logger.warning(f"⚠️ Failed to download image from {url}: {e}")
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
