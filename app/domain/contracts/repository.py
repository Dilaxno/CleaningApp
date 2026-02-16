"""Contract repository - Database operations for contracts"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ...models import BusinessConfig, Client, Contract, User


class ContractRepository:
    """Repository for contract database operations"""

    @staticmethod
    def get_contracts(
        db: Session,
        user_id: int,
        client_id: Optional[int] = None,
        include_all: bool = False,
    ) -> list[Contract]:
        """Get all contracts for a user with optional filters"""
        query = db.query(Contract).filter(Contract.user_id == user_id)

        # Filter by onboarding status unless include_all is True
        if not include_all:
            query = query.filter(Contract.client_onboarding_status == "completed")

        if client_id:
            query = query.filter(Contract.client_id == client_id)

        return query.order_by(Contract.created_at.desc()).all()

    @staticmethod
    def get_contract_by_id(db: Session, contract_id: int, user_id: int) -> Optional[Contract]:
        """Get a specific contract by ID"""
        return (
            db.query(Contract)
            .filter(Contract.id == contract_id, Contract.user_id == user_id)
            .first()
        )

    @staticmethod
    def get_contract_by_public_id(db: Session, public_id: str) -> Optional[Contract]:
        """Get a contract by public UUID"""
        return db.query(Contract).filter(Contract.public_id == public_id).first()

    @staticmethod
    def get_contracts_by_client(db: Session, client_id: int, user_id: int) -> list[Contract]:
        """Get all contracts for a specific client"""
        return (
            db.query(Contract)
            .filter(Contract.client_id == client_id, Contract.user_id == user_id)
            .order_by(Contract.created_at.desc())
            .all()
        )

    @staticmethod
    def create_contract(db: Session, user_id: int, **contract_data) -> Contract:
        """Create a new contract"""
        contract = Contract(user_id=user_id, **contract_data)
        db.add(contract)
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def update_contract(db: Session, contract: Contract, **updates) -> Contract:
        """Update a contract with provided fields"""
        for key, value in updates.items():
            if value is not None and hasattr(contract, key):
                setattr(contract, key, value)

        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def delete_contract(db: Session, contract: Contract) -> None:
        """Delete a contract"""
        db.delete(contract)
        db.commit()

    @staticmethod
    def batch_delete_contracts(db: Session, contract_ids: list[int], user_id: int) -> int:
        """
        Batch delete multiple contracts.
        Returns count of deleted contracts.
        """
        deleted_count = 0

        for contract_id in contract_ids:
            contract = (
                db.query(Contract)
                .filter(Contract.id == contract_id, Contract.user_id == user_id)
                .first()
            )
            if contract:
                db.delete(contract)
                deleted_count += 1

        db.commit()
        return deleted_count

    @staticmethod
    def get_client_by_id(db: Session, client_id: int) -> Optional[Client]:
        """Get a client by ID"""
        return db.query(Client).filter(Client.id == client_id).first()

    @staticmethod
    def get_business_config(db: Session, user_id: int) -> Optional[BusinessConfig]:
        """Get business configuration for a user"""
        return db.query(BusinessConfig).filter(BusinessConfig.user_id == user_id).first()

    @staticmethod
    def get_user_by_firebase_uid(db: Session, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID"""
        return db.query(User).filter(User.firebase_uid == firebase_uid).first()

    @staticmethod
    def update_contract_pdf(
        db: Session, contract: Contract, pdf_key: str, pdf_url: Optional[str] = None
    ) -> Contract:
        """Update contract with PDF information"""
        contract.pdf_key = pdf_key
        if pdf_url:
            contract.pdf_url = pdf_url
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def sign_contract_provider(
        db: Session,
        contract: Contract,
        signature_data: str,
        signed_at: datetime,
    ) -> Contract:
        """Sign contract as provider"""
        contract.provider_signature = signature_data
        contract.provider_signed_at = signed_at
        contract.signed_at = signed_at
        contract.status = "provider_signed"
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def mark_contract_fully_executed(db: Session, contract: Contract) -> Contract:
        """Mark contract as fully executed (both parties signed)"""
        contract.status = "fully_executed"
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def update_client_status(db: Session, client: Client, status: str) -> Client:
        """Update client status"""
        client.status = status
        db.commit()
        db.refresh(client)
        return client
