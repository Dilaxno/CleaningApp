"""Client service - Business logic for client operations"""

import csv
import logging
from datetime import datetime
from io import StringIO
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...models import Client, User
from ...plan_limits import can_add_client, decrement_client_count
from .repository import ClientRepository
from .schemas import ClientCreate, ClientUpdate

logger = logging.getLogger(__name__)


class ClientService:
    """Service layer for client business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ClientRepository()

    def get_clients(self, user: User) -> list[Client]:
        """Get all clients for a user"""
        return self.repo.get_clients(self.db, user.id)

    def get_client(self, client_id: int, user: User) -> Client:
        """Get a specific client"""
        client = self.repo.get_client_by_id(self.db, client_id, user.id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client

    def create_client(self, data: ClientCreate, user: User) -> Client:
        """Create a new client with validation"""
        logger.info(f"📥 Creating client for user_id: {user.id}")

        # Check client limit
        can_add, error_message = can_add_client(user, self.db)
        if not can_add:
            logger.warning(f"⚠️ User {user.id} reached client limit: {error_message}")
            raise HTTPException(status_code=403, detail=error_message)

        # Create client
        client_data = {
            "business_name": data.businessName,
            "contact_name": data.contactName,
            "email": data.email,
            "phone": data.phone,
            "property_type": data.propertyType,
            "property_size": data.propertySize,
            "frequency": data.frequency,
            "notes": data.notes,
            "status": "new_lead",
        }

        return self.repo.create_client(self.db, user.id, **client_data)

    def update_client(self, client_id: int, data: ClientUpdate, user: User) -> Client:
        """Update a client"""
        client = self.get_client(client_id, user)

        updates = {}
        if data.businessName is not None:
            updates["business_name"] = data.businessName
        if data.contactName is not None:
            updates["contact_name"] = data.contactName
        if data.email is not None:
            updates["email"] = data.email
        if data.phone is not None:
            updates["phone"] = data.phone
        if data.propertyType is not None:
            updates["property_type"] = data.propertyType
        if data.propertySize is not None:
            updates["property_size"] = data.propertySize
        if data.frequency is not None:
            updates["frequency"] = data.frequency
        if data.status is not None:
            updates["status"] = data.status
        if data.notes is not None:
            updates["notes"] = data.notes

        return self.repo.update_client(self.db, client, **updates)

    def delete_client(self, client_id: int, user: User) -> dict:
        """Delete a client"""
        client = self.get_client(client_id, user)

        # Check if client has signed the contract
        has_signed_contract = any(
            c.client_signature or c.client_signature_timestamp for c in client.contracts
        )

        self.repo.delete_client(self.db, client)

        # Decrement client count if they had signed
        if has_signed_contract:
            decrement_client_count(user, self.db)

        return {"message": "Client deleted"}

    def batch_delete_clients(self, client_ids: list[int], user: User) -> dict:
        """Batch delete multiple clients"""
        from ...models_invoice import Invoice

        if not client_ids:
            raise HTTPException(status_code=400, detail="No client IDs provided")

        # Delete invoices first (FK constraint)
        for client_id in client_ids:
            client = self.repo.get_client_by_id(self.db, client_id, user.id)
            if client:
                contract_ids = [c.id for c in client.contracts]
                if contract_ids:
                    self.db.query(Invoice).filter(Invoice.contract_id.in_(contract_ids)).delete(
                        synchronize_session=False
                    )

        # Delete clients
        deleted_count, signed_clients_count = self.repo.batch_delete_clients(
            self.db, client_ids, user.id
        )

        # Decrement client count for signed clients
        for _ in range(signed_clients_count):
            decrement_client_count(user, self.db)

        return {
            "message": f"Successfully deleted {deleted_count} client(s)",
            "deletedCount": deleted_count,
        }

    def export_clients_csv(
        self,
        user: User,
        status: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> StreamingResponse:
        """Export clients as CSV"""
        try:
            logger.info(f"📊 CSV Export requested by user {user.id} ({user.email})")

            # Parse dates
            start_dt = None
            end_dt = None
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                except ValueError as e:
                    logger.warning(f"Invalid start_date format: {start_date} - {e}")

            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                except ValueError as e:
                    logger.warning(f"Invalid end_date format: {end_date} - {e}")

            # Get filtered clients
            clients = self.repo.search_clients(self.db, user.id, status, search, start_dt, end_dt)
            logger.info(f"Found {len(clients)} clients to export")

            # Create CSV
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "ID",
                    "Business Name",
                    "Contact Name",
                    "Email",
                    "Phone",
                    "Property Type",
                    "Property Size (sq ft)",
                    "Frequency",
                    "Status",
                    "Notes",
                    "Created At",
                ]
            )

            # Write data
            for client in clients:
                writer.writerow(
                    [
                        client.id,
                        client.business_name or "",
                        client.contact_name or "",
                        client.email or "",
                        client.phone or "",
                        client.property_type or "",
                        client.property_size or "",
                        client.frequency or "",
                        client.status or "",
                        client.notes or "",
                        (
                            client.created_at.strftime("%Y-%m-%d %H:%M:%S")
                            if client.created_at
                            else ""
                        ),
                    ]
                )

            # Prepare response
            output.seek(0)
            filename = f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            logger.info(f"✅ CSV export successful: {filename} ({len(clients)} clients)")

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Cache-Control": "no-cache",
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ CSV export failed for user {user.id}: {str(e)}")
            logger.exception(e)
            raise HTTPException(
                status_code=500, detail="Failed to export clients. Please try again."
            )

    # Quote Request Methods
    def get_quote_requests(self, user: User, status: Optional[str] = None) -> dict:
        """Get quote requests for provider dashboard"""
        clients = self.repo.get_quote_requests(self.db, user.id, status)

        quote_requests = []
        for client in clients:
            quote_requests.append(
                {
                    "id": client.id,
                    "public_id": client.public_id,
                    "business_name": client.business_name,
                    "contact_name": client.contact_name,
                    "email": client.email,
                    "phone": client.phone,
                    "property_type": client.property_type,
                    "property_size": client.property_size,
                    "frequency": client.frequency,
                    "quote_status": client.quote_status,
                    "quote_submitted_at": (
                        client.quote_submitted_at.isoformat() if client.quote_submitted_at else None
                    ),
                    "quote_approved_at": (
                        client.quote_approved_at.isoformat() if client.quote_approved_at else None
                    ),
                    "original_quote_amount": client.original_quote_amount,
                    "adjusted_quote_amount": client.adjusted_quote_amount,
                    "quote_adjustment_notes": client.quote_adjustment_notes,
                    "form_data": client.form_data,
                    "created_at": client.created_at.isoformat() if client.created_at else None,
                }
            )

        return {
            "quote_requests": quote_requests,
            "total": len(quote_requests),
        }

    def get_quote_stats(self, user: User) -> dict:
        """Get quote request statistics"""
        return self.repo.get_quote_stats(self.db, user.id)

    def get_quote_request_detail(self, client_id: int, user: User) -> dict:
        """Get detailed quote request information"""
        client = self.get_client(client_id, user)

        # Get quote history
        history = self.repo.get_quote_history(self.db, client_id)
        history_entries = []
        for entry in history:
            history_entries.append(
                {
                    "id": entry.id,
                    "action": entry.action,
                    "amount": entry.amount,
                    "notes": entry.notes,
                    "created_by": entry.created_by,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                }
            )

        # Process form data (property shots, virtual walkthrough)
        form_data = client.form_data or {}
        form_data = self._process_media_urls(form_data)

        return {
            "id": client.id,
            "public_id": client.public_id,
            "business_name": client.business_name,
            "contact_name": client.contact_name,
            "email": client.email,
            "phone": client.phone,
            "property_type": client.property_type,
            "property_size": client.property_size,
            "frequency": client.frequency,
            "status": client.status,
            "quote_status": client.quote_status,
            "quote_submitted_at": (
                client.quote_submitted_at.isoformat() if client.quote_submitted_at else None
            ),
            "quote_approved_at": (
                client.quote_approved_at.isoformat() if client.quote_approved_at else None
            ),
            "quote_approved_by": client.quote_approved_by,
            "original_quote_amount": client.original_quote_amount,
            "adjusted_quote_amount": client.adjusted_quote_amount,
            "quote_adjustment_notes": client.quote_adjustment_notes,
            "form_data": form_data,
            "notes": client.notes,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
            "history": history_entries,
        }

    def batch_delete_quote_requests(self, quote_request_ids: list[int], user: User) -> dict:
        """Batch delete quote requests"""
        if not quote_request_ids:
            raise HTTPException(status_code=400, detail="No quote request IDs provided")

        deleted_count = 0
        for client_id in quote_request_ids:
            client = self.repo.get_client_by_id(self.db, client_id, user.id)
            if client:
                self.repo.delete_client(self.db, client)
                deleted_count += 1

        logger.info(f"✅ User {user.id} deleted {deleted_count} quote requests")

        return {
            "message": f"Successfully deleted {deleted_count} quote request(s)",
            "deletedCount": deleted_count,
        }

    def _process_media_urls(self, form_data: dict) -> dict:
        """Convert S3 keys to presigned URLs for property shots and videos"""
        from ...routes.upload import generate_presigned_url

        # Process property shots
        if form_data.get("propertyShots"):
            property_shots_keys = form_data.get("propertyShots", [])
            if isinstance(property_shots_keys, str):
                property_shots_keys = [property_shots_keys]

            property_shots_urls = []
            for key in property_shots_keys:
                try:
                    url = generate_presigned_url(key, expiration=3600)
                    property_shots_urls.append(url)
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for key {key}: {e}")
                    continue

            form_data["propertyShots"] = property_shots_urls

        # Process virtual walkthrough
        if form_data.get("virtualWalkthrough"):
            video_key = form_data.get("virtualWalkthrough")
            if isinstance(video_key, str):
                try:
                    video_url = generate_presigned_url(video_key, expiration=7200)
                    form_data["virtualWalkthrough"] = video_url
                    logger.info(f"✅ Generated presigned URL for virtual walkthrough: {video_key}")
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for video {video_key}: {e}")

        return form_data
