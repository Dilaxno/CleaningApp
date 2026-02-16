"""Client router - FastAPI endpoints for client operations"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models import User
from .schemas import (
    BatchDeleteQuoteRequestsRequest,
    BatchDeleteRequest,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
)
from .service import ClientService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["Clients"])


def get_client_service(db: Session = Depends(get_db)) -> ClientService:
    """Dependency injection for ClientService"""
    return ClientService(db)


# ============================================================================
# CORE CRUD OPERATIONS
# ============================================================================


@router.get("", response_model=list[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Get all clients for the current user (excludes pending_signature clients)"""
    clients = service.get_clients(current_user)
    return [
        ClientResponse(
            id=c.id,
            public_id=c.public_id,
            businessName=c.business_name,
            contactName=c.contact_name,
            email=c.email,
            phone=c.phone,
            propertyType=c.property_type,
            propertySize=c.property_size,
            frequency=c.frequency,
            status=c.status,
            notes=c.notes,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.get("/export")
async def export_clients_csv(
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Export clients as CSV with optional filters"""
    return service.export_clients_csv(current_user, status, search, start_date, end_date)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Get a specific client with detailed information"""
    client = service.get_client(client_id, current_user)
    return ClientResponse(
        id=client.id,
        public_id=client.public_id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes,
        created_at=client.created_at,
        form_data=client.form_data,
    )


@router.post("", response_model=ClientResponse)
async def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Create a new client"""
    client = service.create_client(data, current_user)
    return ClientResponse(
        id=client.id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes,
        created_at=client.created_at,
    )


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Update a client"""
    client = service.update_client(client_id, data, current_user)
    return ClientResponse(
        id=client.id,
        businessName=client.business_name,
        contactName=client.contact_name,
        email=client.email,
        phone=client.phone,
        propertyType=client.property_type,
        propertySize=client.property_size,
        frequency=client.frequency,
        status=client.status,
        notes=client.notes,
        created_at=client.created_at,
    )


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Delete a client"""
    return service.delete_client(client_id, current_user)


@router.post("/batch-delete")
async def batch_delete_clients(
    data: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Batch delete multiple clients"""
    return service.batch_delete_clients(data.clientIds, current_user)


# ============================================================================
# QUOTE REQUESTS ROUTES
# ============================================================================


@router.get("/quote-requests/stats/summary")
async def get_quote_requests_stats(
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Get summary statistics for quote requests"""
    return service.get_quote_stats(current_user)


@router.get("/quote-requests")
async def get_quote_requests(
    status: Optional[str] = Query(None, description="Filter by quote status"),
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Get all quote requests for the provider dashboard"""
    return service.get_quote_requests(current_user, status)


@router.get("/quote-requests/{client_id}")
async def get_quote_request_detail(
    client_id: int,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Get detailed information about a specific quote request"""
    return service.get_quote_request_detail(client_id, current_user)


@router.post("/quote-requests/batch-delete")
async def batch_delete_quote_requests(
    data: BatchDeleteQuoteRequestsRequest,
    current_user: User = Depends(get_current_user),
    service: ClientService = Depends(get_client_service),
):
    """Batch delete multiple quote requests"""
    return service.batch_delete_quote_requests(data.quoteRequestIds, current_user)


# ============================================================================
# PUBLIC ROUTES (TODO: Refactor in future phase)
# ============================================================================
# Note: Public routes (quote preview, form submission, contract signing, etc.)
# are temporarily kept in the archived clients.py file.
# These will be refactored when we extract the contracts domain.
# For now, they need to be registered separately in main.py or moved to a
# separate public_clients.py file.

__all__ = [
    "router",
    "get_clients",
    "get_client",
    "create_client",
    "update_client",
    "delete_client",
    "batch_delete_clients",
    "export_clients_csv",
    "get_quote_requests",
    "get_quote_requests_stats",
    "get_quote_request_detail",
    "batch_delete_quote_requests",
]
