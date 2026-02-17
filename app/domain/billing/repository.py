"""Billing repository - Database operations for billing"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ...models import Client, Contract, Schedule, User


class BillingRepository:
    """Repository for billing database operations"""

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_firebase_uid(db: Session, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID"""
        return db.query(User).filter(User.firebase_uid == firebase_uid).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_dodo_customer_id(db: Session, dodo_customer_id: str) -> Optional[User]:
        """Get user by Dodo customer ID"""
        return db.query(User).filter(User.dodo_customer_id == dodo_customer_id).first()

    @staticmethod
    def update_user_plan(
        db: Session,
        user: User,
        plan: Optional[str] = None,
        billing_cycle: Optional[str] = None,
        subscription_status: Optional[str] = None,
        dodo_customer_id: Optional[str] = None,
        dodo_subscription_id: Optional[str] = None,
    ) -> User:
        """Update user billing information"""
        if plan is not None:
            user.plan = plan
        if billing_cycle is not None:
            user.billing_cycle = billing_cycle
        if subscription_status is not None:
            user.subscription_status = subscription_status
        if dodo_customer_id is not None:
            user.dodo_customer_id = dodo_customer_id
        if dodo_subscription_id is not None:
            # Map dodo_subscription_id to subscription_id field in User model
            user.subscription_id = dodo_subscription_id

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_usage_counts(db: Session, user_id: int, start_date: Optional[datetime] = None) -> dict:
        """Get usage counts for clients, contracts, and schedules"""
        query_clients = db.query(Client).filter(Client.user_id == user_id)
        query_contracts = db.query(Contract).filter(Contract.user_id == user_id)
        query_schedules = db.query(Schedule).filter(Schedule.user_id == user_id)

        if start_date:
            query_clients = query_clients.filter(Client.created_at >= start_date)
            query_contracts = query_contracts.filter(Contract.created_at >= start_date)
            query_schedules = query_schedules.filter(Schedule.created_at >= start_date)

        return {
            "clients_count": query_clients.count(),
            "contracts_count": query_contracts.count(),
            "schedules_count": query_schedules.count(),
        }

    @staticmethod
    def get_total_counts(db: Session, user_id: int) -> dict:
        """Get total counts (all time) for clients, contracts, and schedules"""
        return {
            "clients_count": db.query(Client).filter(Client.user_id == user_id).count(),
            "contracts_count": db.query(Contract).filter(Contract.user_id == user_id).count(),
            "schedules_count": db.query(Schedule).filter(Contract.user_id == user_id).count(),
        }
