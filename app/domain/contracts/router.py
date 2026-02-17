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
