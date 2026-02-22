"""Contract router - FastAPI endpoints for contract operations"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from ...routes.upload import generate_presigned_url
from .pdf_service import ContractPDFService
from .schemas import (
    BatchDeleteRequest,
    ContractCreate,
    ContractResponse,
    ContractUpdate,
    ProviderSignatureRequest,
)
from .service import ContractService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contracts"])


def get_contract_service(db: Session = Depends(get_db)) -> ContractService:
    """Dependency injection for ContractService"""
    return ContractService(db)


# ============================================================================
# CORE CRUD OPERATIONS
# ============================================================================


@router.get("", response_model=list[ContractResponse])
async def get_contracts(
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
    client_id: Optional[int] = Query(None, description="Filter contracts by client ID"),
    include_all: bool = Query(False, description="Include contracts in all onboarding statuses"),
):
    """Get all contracts for the current user"""
    contracts = service.get_contracts(current_user, client_id, include_all)

    # Get provider's default signature
    business_config = service.repo.get_business_config(service.db, current_user.id)
    default_signature_url = None
    if business_config and business_config.signature_url:
        try:
            default_signature_url = generate_presigned_url(business_config.signature_url)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for default signature: {e}")

    result = []
    for contract in contracts:
        client = service.repo.get_client_by_id(service.db, contract.client_id)
        pdf_url = ContractPDFService.get_pdf_url(contract.pdf_key, contract.public_id)

        result.append(
            ContractResponse(
                id=contract.id,
                public_id=contract.public_id,
                clientId=contract.client_id,
                clientPublicId=client.public_id if client else None,
                clientName=client.business_name if client else "Unknown",
                clientEmail=client.email if client else None,
                title=contract.title,
                description=contract.description,
                contractType=contract.contract_type,
                status=contract.status,
                startDate=contract.start_date,
                endDate=contract.end_date,
                totalValue=contract.total_value,
                paymentTerms=contract.payment_terms,
                termsConditions=contract.terms_conditions,
                pdfUrl=pdf_url,
                hasPdf=bool(contract.pdf_key),
                providerSignature=contract.provider_signature,
                signedAt=contract.signed_at,
                clientSignatureTimestamp=contract.client_signature_timestamp,
                providerSignedAt=contract.provider_signed_at,
                createdAt=contract.created_at,
                defaultSignatureUrl=default_signature_url,
            )
        )

    return result


@router.post("/initiate", response_model=dict)
async def initiate_contract_process(
    data: ContractCreate,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Initiate contract process (creates draft contract)"""
    contract = service.create_contract(data, current_user)
    return {
        "message": "Contract initiated successfully",
        "contractId": contract.id,
        "status": contract.status,
    }


@router.post("", response_model=ContractResponse)
async def create_contract(
    data: ContractCreate,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Create a new contract"""
    contract = service.create_contract(data, current_user)
    client = service.repo.get_client_by_id(service.db, contract.client_id)

    return ContractResponse(
        id=contract.id,
        public_id=contract.public_id,
        clientId=contract.client_id,
        clientPublicId=client.public_id if client else None,
        clientName=client.business_name if client else "Unknown",
        clientEmail=client.email if client else None,
        title=contract.title,
        description=contract.description,
        contractType=contract.contract_type,
        status=contract.status,
        startDate=contract.start_date,
        endDate=contract.end_date,
        totalValue=contract.total_value,
        paymentTerms=contract.payment_terms,
        termsConditions=contract.terms_conditions,
        pdfUrl=None,
        hasPdf=False,
        providerSignature=contract.provider_signature,
        signedAt=contract.signed_at,
        clientSignatureTimestamp=contract.client_signature_timestamp,
        providerSignedAt=contract.provider_signed_at,
        createdAt=contract.created_at,
    )


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Update a contract"""
    contract = service.update_contract(contract_id, data, current_user)
    client = service.repo.get_client_by_id(service.db, contract.client_id)
    pdf_url = ContractPDFService.get_pdf_url(contract.pdf_key, contract.public_id)

    return ContractResponse(
        id=contract.id,
        public_id=contract.public_id,
        clientId=contract.client_id,
        clientPublicId=client.public_id if client else None,
        clientName=client.business_name if client else "Unknown",
        clientEmail=client.email if client else None,
        title=contract.title,
        description=contract.description,
        contractType=contract.contract_type,
        status=contract.status,
        startDate=contract.start_date,
        endDate=contract.end_date,
        totalValue=contract.total_value,
        paymentTerms=contract.payment_terms,
        termsConditions=contract.terms_conditions,
        pdfUrl=pdf_url,
        hasPdf=bool(contract.pdf_key),
        providerSignature=contract.provider_signature,
        signedAt=contract.signed_at,
        clientSignatureTimestamp=contract.client_signature_timestamp,
        providerSignedAt=contract.provider_signed_at,
        createdAt=contract.created_at,
    )


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Delete a contract"""
    return service.delete_contract(contract_id, current_user)


@router.post("/batch-delete")
async def batch_delete_contracts(
    data: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Batch delete multiple contracts"""
    return service.batch_delete_contracts(data.contract_ids, current_user)


# ============================================================================
# CONTRACT SIGNING
# ============================================================================


@router.post("/{contract_id}/sign-provider")
async def sign_contract_as_provider(
    contract_id: int,
    signature_request: ProviderSignatureRequest,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Sign contract as provider"""
    return await service.sign_contract_as_provider(contract_id, signature_request, current_user)


@router.post("/{contract_id}/provider-sign")
async def provider_sign_contract(
    contract_id: int,
    signature_request: ProviderSignatureRequest,
    current_user: User = Depends(get_current_user),
    service: ContractService = Depends(get_contract_service),
):
    """Alternative endpoint for provider signing (alias)"""
    return await service.sign_contract_as_provider(contract_id, signature_request, current_user)


# ============================================================================
# CONTRACT DOWNLOAD (kept from original for backward compatibility)
# ============================================================================
# Note: PDF generation and download routes are kept in the original
# contracts.py and contracts_pdf.py files for now.
# These will be fully integrated in a future refactoring phase.

from ...routes.contracts import (
    download_contract,
    download_contract_by_public_id,
    send_square_invoice_email,
)
from ...routes.contracts_pdf import (
    download_contract_pdf,
    generate_contract_pdf,
    get_contract_pdf,
    preview_contract,
    view_contract_pdf_public,
)

__all__ = [
    "router",
    "get_contracts",
    "create_contract",
    "update_contract",
    "delete_contract",
    "batch_delete_contracts",
    "sign_contract_as_provider",
    "provider_sign_contract",
    # Re-exported from original files
    "generate_contract_pdf",
    "get_contract_pdf",
    "download_contract_pdf",
    "view_contract_pdf_public",
    "preview_contract",
    "download_contract",
    "download_contract_by_public_id",
    "send_square_invoice_email",
]


# ============================================================================
# PUBLIC CONTRACT SIGNING (for clients)
# ============================================================================


@router.post("/public/{contract_public_id}/generate-with-scope")
async def generate_contract_with_scope(
    contract_public_id: str,
    scope_data: dict,
    service: ContractService = Depends(get_contract_service),
):
    """
    Generate contract with Exhibit A - Detailed Scope of Work

    This endpoint:
    1. Stores the scope of work data in the contract
    2. Generates Exhibit A PDF
    3. Uploads it to R2 storage
    4. Updates the contract to reference Exhibit A
    """
    from datetime import datetime
    from fastapi import HTTPException
    from ...models import BusinessConfig, Client, Contract, User
    from ...services.exhibit_a_generator import generate_exhibit_a_pdf
    from ...routes.upload import get_r2_client, R2_BUCKET_NAME

    # Find contract
    contract = service.db.query(Contract).filter(Contract.public_id == contract_public_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get client info
    client = service.db.query(Client).filter(Client.id == contract.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get business info
    user = service.db.query(User).filter(User.id == contract.user_id).first()
    business_config = (
        service.db.query(BusinessConfig).filter(BusinessConfig.user_id == contract.user_id).first()
    )
    business_name = (
        business_config.business_name if business_config else user.full_name or "Service Provider"
    )

    try:
        # Generate Exhibit A PDF
        exhibit_pdf_bytes = await generate_exhibit_a_pdf(
            scope_data=scope_data.get("scope_of_work", {}),
            client_name=client.contact_name or client.business_name,
            business_name=business_name,
            contract_title=contract.title,
        )

        # Upload to R2
        exhibit_filename = (
            f"exhibit_a_{contract.public_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        exhibit_key = f"contracts/{contract.user_id}/{exhibit_filename}"

        # Upload to R2
        r2 = get_r2_client()
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=exhibit_key,
            Body=exhibit_pdf_bytes,
            ContentType="application/pdf",
        )

        # Store scope of work data and exhibit key
        contract.scope_of_work = scope_data.get("scope_of_work", {})
        contract.exhibit_a_pdf_key = exhibit_key

        service.db.commit()
        service.db.refresh(contract)

        logger.info(
            f"✅ Generated Exhibit A for contract {contract.public_id} - Key: {exhibit_key}"
        )

        return {
            "message": "Exhibit A generated successfully",
            "exhibit_key": exhibit_key,
            "contract_id": contract.public_id,
        }

    except Exception as e:
        logger.error(f"❌ Failed to generate Exhibit A for contract {contract.public_id}: {e}")
        service.db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to generate scope of work document: {str(e)}"
        )


@router.post("/public/{contract_public_id}/sign")
async def sign_contract_public(
    contract_public_id: str,
    signature_request: dict,
    service: ContractService = Depends(get_contract_service),
):
    """
    Public endpoint for clients to sign their contract using contract public ID.
    This is used in the quote approval flow where clients schedule first, then sign.
    """
    from datetime import datetime
    from fastapi import HTTPException
    from ...models import BusinessConfig, Client, Contract
    from ...email_service import (
        send_client_signature_confirmation,
        send_contract_signed_notification,
    )

    # Validate signature size
    signature_data = signature_request.get("signature_data", "")
    client_name = signature_request.get("client_name", "")

    if len(signature_data) > 500000:
        raise HTTPException(status_code=400, detail="Signature data too large")

    # Find contract by public_id
    contract = service.db.query(Contract).filter(Contract.public_id == contract_public_id).first()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get client
    client = service.db.query(Client).filter(Client.id == contract.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get user (business owner)
    user = service.db.query(User).filter(User.id == contract.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Business not found")

    # Update contract with client signature
    contract.client_signature = signature_data
    contract.client_signature_timestamp = datetime.utcnow()

    # Keep status as "new" - waiting for provider to review and sign
    # Status will only change to "signed" when provider signs back
    # This allows provider to review the client signature and schedule before finalizing

    service.db.commit()
    service.db.refresh(contract)

    logger.info(
        f"✅ Contract {contract.id} signed by client via public endpoint - awaiting provider signature"
    )

    # Regenerate PDF with client signature
    try:
        from arq import create_pool
        from ...worker import get_redis_settings
        from ...routes.contracts_pdf import calculate_quote, generate_contract_html, html_to_pdf
        from ...routes.upload import get_r2_client
        from ...config import R2_BUCKET_NAME

        logger.info(f"🔄 Regenerating PDF with client signature for contract {contract.id}")

        # Get business config for quote calculation
        business_config = (
            service.db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        )

        # Calculate quote
        quote = calculate_quote(business_config, client.form_data)

        # Generate HTML with client signature
        html_content = await generate_contract_html(
            business_config,
            client,
            client.form_data,
            quote,
            service.db,
            client_signature=signature_data,
            contract_public_id=contract.public_id,
        )

        # Convert to PDF
        pdf_bytes = await html_to_pdf(html_content)

        # Upload to R2
        r2_client = get_r2_client()
        pdf_key = f"contracts/{user.firebase_uid}/{contract.public_id}.pdf"

        r2_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=pdf_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )

        # Update contract with new PDF key
        contract.pdf_key = pdf_key
        service.db.commit()

        logger.info(f"✅ PDF regenerated successfully with client signature: {pdf_key}")

    except Exception as e:
        logger.error(f"❌ Failed to regenerate PDF with client signature: {e}")
        # Don't fail the signing process if PDF regeneration fails
        pass

    # Send confirmation emails
    business_name = "Service Provider"
    business_config = (
        service.db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
    )
    if business_config:
        business_name = business_config.business_name or user.full_name or "Service Provider"

    # Send unified notification (email + SMS) to client
    try:
        from ...services.notification_service import send_contract_signed_notification

        await send_contract_signed_notification(
            db=db,
            user_id=user.id,
            client_email=client.email,
            client_phone=client.phone,
            client_name=client_name,
            business_name=business_name,
            contract_title=contract.title,
            contract_id=contract.id,
            contract_pdf_url=None,
        )
    except Exception as e:
        logger.error(f"Failed to send client notification: {e}")

    # Send notification to provider
    if user.email:
        try:
            await send_contract_signed_notification(
                to=user.email,
                business_name=business_name,
                client_name=client_name,
                contract_title=contract.title,
            )
        except Exception as e:
            logger.error(f"Failed to send provider notification email: {e}")

    return {
        "message": "Contract signed successfully",
        "contract_id": contract.id,
        "contract_public_id": contract.public_id,
        "status": contract.status,
    }
