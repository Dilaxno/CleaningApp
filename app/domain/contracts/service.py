"""Contract service - Business logic for contract operations"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...email_service import (
    send_contract_fully_executed_email,
    send_provider_contract_signed_confirmation,
)
from ...models import BusinessConfig, Contract, User
from ...utils.sanitization import sanitize_string
from ...routes.upload import generate_presigned_url
from .pdf_service import ContractPDFService
from .repository import ContractRepository
from .schemas import ContractCreate, ContractUpdate, ProviderSignatureRequest

logger = logging.getLogger(__name__)


class ContractService:
    """Service layer for contract business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ContractRepository()
        self.pdf_service = ContractPDFService()

    def get_contracts(
        self,
        user: User,
        client_id: Optional[int] = None,
        include_all: bool = False,
    ) -> list[Contract]:
        """Get all contracts for a user"""
        return self.repo.get_contracts(self.db, user.id, client_id, include_all)

    def get_contract(self, contract_id: int, user: User) -> Contract:
        """Get a specific contract"""
        contract = self.repo.get_contract_by_id(self.db, contract_id, user.id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return contract

    def get_contract_by_public_id(self, public_id: str) -> Contract:
        """Get a contract by public UUID"""
        contract = self.repo.get_contract_by_public_id(self.db, public_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return contract

    def create_contract(self, data: ContractCreate, user: User) -> Contract:
        """Create a new contract"""
        logger.info(f"📝 Creating contract for user_id: {user.id}, client_id: {data.clientId}")

        # Verify client exists and belongs to user
        client = self.repo.get_client_by_id(self.db, data.clientId)
        if not client or client.user_id != user.id:
            raise HTTPException(status_code=404, detail="Client not found")

        # Sanitize text inputs
        title = sanitize_string(data.title) if data.title else "Untitled Contract"
        description = sanitize_string(data.description) if data.description else None
        terms_conditions = sanitize_string(data.termsConditions) if data.termsConditions else None

        contract_data = {
            "client_id": data.clientId,
            "title": title,
            "description": description,
            "contract_type": data.contractType,
            "start_date": data.startDate,
            "end_date": data.endDate,
            "total_value": data.totalValue,
            "payment_terms": data.paymentTerms,
            "terms_conditions": terms_conditions,
            "status": "draft",
        }

        return self.repo.create_contract(self.db, user.id, **contract_data)

    def update_contract(self, contract_id: int, data: ContractUpdate, user: User) -> Contract:
        """Update a contract"""
        contract = self.get_contract(contract_id, user)

        updates = {}
        if data.title is not None:
            updates["title"] = sanitize_string(data.title)
        if data.description is not None:
            updates["description"] = sanitize_string(data.description)
        if data.contractType is not None:
            updates["contract_type"] = data.contractType
        if data.status is not None:
            updates["status"] = data.status
        if data.startDate is not None:
            updates["start_date"] = data.startDate
        if data.endDate is not None:
            updates["end_date"] = data.endDate
        if data.totalValue is not None:
            updates["total_value"] = data.totalValue
        if data.paymentTerms is not None:
            updates["payment_terms"] = data.paymentTerms
        if data.termsConditions is not None:
            updates["terms_conditions"] = sanitize_string(data.termsConditions)

        return self.repo.update_contract(self.db, contract, **updates)

    def delete_contract(self, contract_id: int, user: User) -> dict:
        """Delete a contract"""
        contract = self.get_contract(contract_id, user)
        self.repo.delete_contract(self.db, contract)
        return {"message": "Contract deleted successfully"}

    def batch_delete_contracts(self, contract_ids: list[int], user: User) -> dict:
        """Batch delete multiple contracts"""
        if not contract_ids:
            raise HTTPException(status_code=400, detail="No contract IDs provided")

        deleted_count = self.repo.batch_delete_contracts(self.db, contract_ids, user.id)

        logger.info(f"✅ User {user.id} deleted {deleted_count} contracts")

        return {
            "message": f"Successfully deleted {deleted_count} contract(s)",
            "deletedCount": deleted_count,
        }

    async def sign_contract_as_provider(
        self, contract_id: int, signature_request: ProviderSignatureRequest, user: User
    ) -> dict:
        """Sign contract as provider"""
        contract = self.get_contract(contract_id, user)

        # Get signature data
        if signature_request.use_default_signature:
            # Use provider's default signature from business config
            business_config = self.repo.get_business_config(self.db, user.id)
            if not business_config or not business_config.signature_url:
                raise HTTPException(
                    status_code=400,
                    detail="No default signature found. Please upload a signature first.",
                )

            try:
                signature_data = generate_presigned_url(business_config.signature_url)
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for signature: {e}")
                raise HTTPException(status_code=500, detail="Failed to load default signature")
        else:
            signature_data = signature_request.signature_data

        # Sign the contract
        signed_at = datetime.utcnow()
        contract = self.repo.sign_contract_provider(self.db, contract, signature_data, signed_at)

        # Check if both parties have signed
        if contract.client_signature:
            # Both parties signed - mark as fully executed
            contract = self.repo.mark_contract_fully_executed(self.db, contract)

            # Update client onboarding status to pending_scheduling
            contract.client_onboarding_status = "pending_scheduling"

            # Update client status
            client = self.repo.get_client_by_id(self.db, contract.client_id)
            if client:
                self.repo.update_client_status(self.db, client, "active")

            # Get business config for business name
            business_config = (
                self.db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
            )
            business_name = business_config.business_name if business_config else user.email

            # Format public_id as CLN-XXXXXXXX
            formatted_contract_id = (
                f"CLN-{contract.public_id[:8].upper()}" if contract.public_id else f"#{contract.id}"
            )

            # Send unified notification (email + SMS) for fully executed contract
            try:
                from ...services.notification_service import (
                    send_contract_fully_executed_notification,
                )

                await send_contract_fully_executed_notification(
                    db=self.db,
                    user_id=user.id,
                    client_email=client.email,
                    client_phone=client.phone,
                    client_name=client.business_name or client.contact_name,
                    business_name=business_name,
                    contract_title=contract.title or "Service Agreement",
                    contract_id=formatted_contract_id,
                    service_type=contract.contract_type or "Cleaning Service",
                    total_value=contract.total_value,
                )
                logger.info(f"✅ Sent fully executed notification for contract {contract.id}")
            except Exception as e:
                logger.error(f"Failed to send fully executed notification: {e}")

            # Send scheduling invitation to client
            try:
                from ...email_service import send_schedule_invitation_after_signing

                await send_schedule_invitation_after_signing(
                    to=client.email,
                    client_name=client.business_name or client.contact_name,
                    business_name=business_name,
                    contract_title=contract.title or "Service Agreement",
                    contract_id=formatted_contract_id,
                    client_public_id=client.public_id,
                )
                logger.info(f"✅ Sent scheduling invitation for contract {contract.id}")
            except Exception as e:
                logger.error(f"Failed to send scheduling invitation: {e}")

        # Get business config for provider name
        business_config = (
            self.db.query(BusinessConfig).filter(BusinessConfig.user_id == user.id).first()
        )
        provider_name = business_config.business_name if business_config else user.email

        # Send provider confirmation email
        try:
            await send_provider_contract_signed_confirmation(
                to=user.email,
                provider_name=provider_name,
                client_name=contract.client.business_name or contract.client.contact_name,
                contract_id=str(contract.id),
            )
            logger.info(f"✅ Sent provider signature confirmation for contract {contract.id}")
        except Exception as e:
            logger.error(f"Failed to send provider confirmation email: {e}")

        return {
            "message": "Contract signed successfully",
            "status": contract.status,
            "fullyExecuted": contract.status == "signed",
            # Return full contract data for frontend
            "id": contract.id,
            "title": contract.title,
            "description": contract.description,
            "clientName": contract.client.business_name or contract.client.contact_name,
            "clientId": contract.client_id,
            "totalValue": contract.total_value,
            "status": contract.status,
            "pdfUrl": self.pdf_service.get_pdf_url(contract.pdf_key, contract.public_id),
            "signedAt": contract.signed_at.isoformat() if contract.signed_at else None,
            "clientSignatureTimestamp": (
                contract.client_signature_timestamp.isoformat()
                if contract.client_signature_timestamp
                else None
            ),
            "providerSignedAt": (
                contract.provider_signed_at.isoformat() if contract.provider_signed_at else None
            ),
            "createdAt": contract.created_at.isoformat() if contract.created_at else None,
            "defaultSignatureUrl": (business_config.signature_url if business_config else None),
        }

    def get_contract_with_details(self, contract_id: int, user: User) -> dict:
        """Get contract with full details including client and PDF info"""
        contract = self.get_contract(contract_id, user)

        # Get client details
        client = self.repo.get_client_by_id(self.db, contract.client_id)

        # Get PDF URL
        pdf_url = self.pdf_service.get_pdf_url(contract.pdf_key, contract.public_id)

        # Get default signature URL
        business_config = self.repo.get_business_config(self.db, user.id)
        default_signature_url = None
        if business_config and business_config.signature_url:
            try:
                default_signature_url = generate_presigned_url(business_config.signature_url)
            except Exception as e:
                logger.warning(f"Failed to generate presigned URL for default signature: {e}")

        return {
            "id": contract.id,
            "public_id": contract.public_id,
            "clientId": contract.client_id,
            "clientPublicId": client.public_id if client else None,
            "clientName": client.business_name if client else "Unknown",
            "clientEmail": client.email if client else None,
            "title": contract.title,
            "description": contract.description,
            "contractType": contract.contract_type,
            "status": contract.status,
            "startDate": contract.start_date,
            "endDate": contract.end_date,
            "totalValue": contract.total_value,
            "paymentTerms": contract.payment_terms,
            "termsConditions": contract.terms_conditions,
            "pdfUrl": pdf_url,
            "hasPdf": bool(contract.pdf_key),
            "providerSignature": contract.provider_signature,
            "signedAt": contract.signed_at,
            "clientSignatureTimestamp": contract.client_signature_timestamp,
            "providerSignedAt": contract.provider_signed_at,
            "createdAt": contract.created_at,
            "defaultSignatureUrl": default_signature_url,
        }
