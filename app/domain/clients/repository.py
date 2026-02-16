"""Client repository - Database operations for clients"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ...models import Client, QuoteHistory, User


class ClientRepository:
    """Repository for client database operations"""

    @staticmethod
    def get_clients(db: Session, user_id: int, exclude_pending_signature: bool = True) -> list[Client]:
        """Get all clients for a user"""
        query = db.query(Client).filter(Client.user_id == user_id)
        
        if exclude_pending_signature:
            query = query.filter(Client.status != "pending_signature")
        
        return query.order_by(Client.created_at.desc()).all()

    @staticmethod
    def get_client_by_id(db: Session, client_id: int, user_id: int) -> Optional[Client]:
        """Get a specific client by ID"""
        return (
            db.query(Client)
            .filter(Client.id == client_id, Client.user_id == user_id)
            .first()
        )

    @staticmethod
    def get_client_by_public_id(db: Session, public_id: str) -> Optional[Client]:
        """Get a client by public UUID"""
        return db.query(Client).filter(Client.public_id == public_id).first()

    @staticmethod
    def create_client(db: Session, user_id: int, **client_data) -> Client:
        """Create a new client"""
        client = Client(user_id=user_id, **client_data)
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def update_client(db: Session, client: Client, **updates) -> Client:
        """Update a client with provided fields"""
        for key, value in updates.items():
            if value is not None and hasattr(client, key):
                setattr(client, key, value)
        
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def delete_client(db: Session, client: Client) -> None:
        """Delete a client"""
        db.delete(client)
        db.commit()

    @staticmethod
    def batch_delete_clients(db: Session, client_ids: list[int], user_id: int) -> tuple[int, int]:
        """
        Batch delete multiple clients.
        Returns (deleted_count, signed_clients_count)
        """
        deleted_count = 0
        signed_clients_count = 0

        for client_id in client_ids:
            client = (
                db.query(Client)
                .filter(Client.id == client_id, Client.user_id == user_id)
                .first()
            )
            if client:
                # Check if client has signed the contract
                has_signed_contract = any(
                    c.client_signature or c.client_signature_timestamp 
                    for c in client.contracts
                )
                if has_signed_contract:
                    signed_clients_count += 1

                db.delete(client)
                deleted_count += 1

        db.commit()
        return deleted_count, signed_clients_count

    # Quote Request Methods
    @staticmethod
    def get_quote_requests(
        db: Session, 
        user_id: int, 
        status: Optional[str] = None
    ) -> list[Client]:
        """Get quote requests with optional status filter"""
        query = db.query(Client).filter(Client.user_id == user_id)

        if status:
            query = query.filter(Client.quote_status == status)
        else:
            query = query.filter(Client.quote_status == "pending_review")

        return query.order_by(Client.quote_submitted_at.desc()).all()

    @staticmethod
    def get_quote_stats(db: Session, user_id: int) -> dict:
        """Get quote request statistics"""
        pending_count = (
            db.query(func.count(Client.id))
            .filter(Client.user_id == user_id, Client.quote_status == "pending_review")
            .scalar()
        )

        approved_count = (
            db.query(func.count(Client.id))
            .filter(Client.user_id == user_id, Client.quote_status == "approved")
            .scalar()
        )

        adjusted_count = (
            db.query(func.count(Client.id))
            .filter(Client.user_id == user_id, Client.quote_status == "adjusted")
            .scalar()
        )

        rejected_count = (
            db.query(func.count(Client.id))
            .filter(Client.user_id == user_id, Client.quote_status == "rejected")
            .scalar()
        )

        total_pending_value = (
            db.query(func.sum(Client.original_quote_amount))
            .filter(Client.user_id == user_id, Client.quote_status == "pending_review")
            .scalar()
            or 0
        )

        return {
            "pending_count": pending_count,
            "approved_count": approved_count,
            "adjusted_count": adjusted_count,
            "rejected_count": rejected_count,
            "total_pending_value": float(total_pending_value),
        }

    @staticmethod
    def get_quote_history(db: Session, client_id: int) -> list[QuoteHistory]:
        """Get quote history for a client"""
        return (
            db.query(QuoteHistory)
            .filter(QuoteHistory.client_id == client_id)
            .order_by(QuoteHistory.created_at.desc())
            .all()
        )

    # Search and Filter Methods
    @staticmethod
    def search_clients(
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Client]:
        """Search and filter clients"""
        query = db.query(Client).filter(
            Client.user_id == user_id, 
            Client.status != "pending_signature"
        )

        if status and status != "all":
            query = query.filter(Client.status == status)

        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                (Client.business_name.ilike(search_term))
                | (Client.contact_name.ilike(search_term))
                | (Client.email.ilike(search_term))
            )

        if start_date:
            query = query.filter(Client.created_at >= start_date)

        if end_date:
            query = query.filter(Client.created_at <= end_date)

        return query.order_by(Client.created_at.desc()).all()

    @staticmethod
    def get_user_by_firebase_uid(db: Session, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID"""
        return db.query(User).filter(User.firebase_uid == firebase_uid).first()
