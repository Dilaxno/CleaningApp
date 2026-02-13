"""
QuickBooks OAuth and Sync Integration
Handles OAuth connection and automatic syncing of invoices, payments, and customers
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import FRONTEND_URL, SECRET_KEY
from ..database import get_db
from ..models import Client, Contract, User
from ..models_quickbooks import QuickBooksIntegration, QuickBooksSyncLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])

# QuickBooks Configuration
QUICKBOOKS_ENVIRONMENT = os.getenv("QUICKBOOKS_ENVIRONMENT", "production")
QUICKBOOKS_CLIENT_ID = os.getenv("QUICKBOOKS_CLIENT_ID")
QUICKBOOKS_CLIENT_SECRET = os.getenv("QUICKBOOKS_CLIENT_SECRET")
QUICKBOOKS_REDIRECT_URI = os.getenv(
    "QUICKBOOKS_REDIRECT_URI", f"{FRONTEND_URL}/auth/quickbooks/callback"
)

# QuickBooks API URLs
if QUICKBOOKS_ENVIRONMENT == "production":
    QUICKBOOKS_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
    QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QUICKBOOKS_API_BASE_URL = "https://quickbooks.api.intuit.com/v3"
    QUICKBOOKS_DISCOVERY_URL = "https://developer.api.intuit.com/.well-known/openid_configuration"
else:
    QUICKBOOKS_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
    QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QUICKBOOKS_API_BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3"
    QUICKBOOKS_DISCOVERY_URL = (
        "https://developer.api.intuit.com/.well-known/openid_sandbox_configuration"
    )

# Encryption for tokens
cipher_suite = Fernet(SECRET_KEY.encode()[:44].ljust(44, b"="))


# Pydantic Models
class QuickBooksStatusResponse(BaseModel):
    connected: bool
    realm_id: Optional[str] = None
    company_name: Optional[str] = None
    auto_sync_enabled: Optional[bool] = None


class QuickBooksSyncSettings(BaseModel):
    auto_sync_enabled: bool
    sync_invoices: bool
    sync_payments: bool
    sync_customers: bool


# Helper Functions
def encrypt_token(token: str) -> str:
    """Encrypt a token for storage"""
    return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


async def get_quickbooks_integration(user_id: int, db: Session) -> Optional[QuickBooksIntegration]:
    """Get active QuickBooks integration for user"""
    return db.query(QuickBooksIntegration).filter(QuickBooksIntegration.user_id == user_id).first()


async def refresh_access_token(integration: QuickBooksIntegration, db: Session) -> str:
    """Refresh QuickBooks access token if expired"""
    if integration.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
        return decrypt_token(integration.access_token)

    try:
        refresh_token = decrypt_token(integration.refresh_token)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                QUICKBOOKS_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {get_basic_auth_header()}",
                },
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise HTTPException(status_code=401, detail="Failed to refresh QuickBooks token")

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            # Update stored tokens
            integration.access_token = encrypt_token(new_access_token)
            integration.refresh_token = encrypt_token(new_refresh_token)
            integration.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            integration.updated_at = datetime.utcnow()
            db.commit()

            return new_access_token

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Failed to refresh QuickBooks token") from e


def get_basic_auth_header() -> str:
    """Generate Basic Auth header for QuickBooks"""
    import base64

    credentials = f"{QUICKBOOKS_CLIENT_ID}:{QUICKBOOKS_CLIENT_SECRET}"
    return base64.b64encode(credentials.encode()).decode()


# Routes
@router.post("/oauth/initiate")
async def initiate_oauth(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Initiate QuickBooks OAuth 2.0 flow
    Returns authorization URL
    """
    if not QUICKBOOKS_CLIENT_ID:
        raise HTTPException(status_code=500, detail="QuickBooks not configured")

    # Generate CSRF state token for security
    state = secrets.token_urlsafe(32)

    # QuickBooks OAuth scopes
    scope = "com.intuit.quickbooks.accounting"

    # Build OAuth URL
    oauth_url = (
        f"{QUICKBOOKS_AUTH_URL}"
        f"?client_id={QUICKBOOKS_CLIENT_ID}"
        f"&response_type=code"
        f"&scope={quote(scope)}"
        f"&redirect_uri={quote(QUICKBOOKS_REDIRECT_URI)}"
        f"&state={state}"
    )

    logger.info(f"QuickBooks OAuth initiated for user: {current_user.email}")
    logger.info(f"Environment: {QUICKBOOKS_ENVIRONMENT}")

    return {"oauth_url": oauth_url, "state": state}


@router.get("/callback-handler")
async def oauth_callback_handler(
    code: str,
    realmId: str,
    state: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Complete QuickBooks OAuth 2.0 flow
    Called by frontend after QuickBooks redirects with authorization code
    """
    if not QUICKBOOKS_CLIENT_ID or not QUICKBOOKS_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="QuickBooks not configured")

    try:
        logger.info(f"QuickBooks OAuth callback for user: {current_user.email}")
        logger.info(f"Realm ID: {realmId}")

        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QUICKBOOKS_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {get_basic_auth_header()}",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": QUICKBOOKS_REDIRECT_URI,
                },
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"QuickBooks token exchange failed: {error_detail}")
                raise HTTPException(
                    status_code=400, detail=f"Failed to exchange authorization code: {error_detail}"
                )

            token_data = response.json()

        # Extract tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token or not refresh_token:
            raise HTTPException(status_code=400, detail="Invalid token response from QuickBooks")

        # Get company info
        company_name = None
        try:
            async with httpx.AsyncClient() as client:
                company_response = await client.get(
                    f"{QUICKBOOKS_API_BASE_URL}/company/{realmId}/companyinfo/{realmId}",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                    },
                )
                if company_response.status_code == 200:
                    company_data = company_response.json()
                    company_name = company_data.get("CompanyInfo", {}).get("CompanyName")
        except Exception as e:
            logger.warning(f"Failed to fetch company info: {e}")

        # Encrypt tokens
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token)

        # Calculate token expiration
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Store or update integration
        integration = await get_quickbooks_integration(current_user.id, db)

        if integration:
            integration.realm_id = realmId
            integration.company_name = company_name
            integration.access_token = encrypted_access_token
            integration.refresh_token = encrypted_refresh_token
            integration.token_expires_at = token_expires_at
            integration.environment = QUICKBOOKS_ENVIRONMENT
            integration.updated_at = datetime.utcnow()
        else:
            integration = QuickBooksIntegration(
                user_id=current_user.id,
                realm_id=realmId,
                company_name=company_name,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expires_at=token_expires_at,
                environment=QUICKBOOKS_ENVIRONMENT,
                auto_sync_enabled=True,
                sync_invoices=True,
                sync_payments=True,
                sync_customers=True,
            )
            db.add(integration)

        db.commit()

        logger.info(f"✅ QuickBooks connected successfully for user: {current_user.email}")

        return {"success": True, "realm_id": realmId, "company_name": company_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks OAuth callback error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to complete QuickBooks connection"
        ) from e


@router.get("/status")
async def get_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if user has QuickBooks connected"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if integration:
        return QuickBooksStatusResponse(
            connected=True,
            realm_id=integration.realm_id,
            company_name=integration.company_name,
            auto_sync_enabled=integration.auto_sync_enabled,
        )

    return QuickBooksStatusResponse(connected=False)


@router.post("/disconnect")
async def disconnect(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Disconnect QuickBooks integration"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration:
        raise HTTPException(status_code=404, detail="QuickBooks not connected")

    try:
        # Revoke token with QuickBooks
        access_token = decrypt_token(integration.access_token)

        async with httpx.AsyncClient() as client:
            await client.post(
                "https://developer.api.intuit.com/v2/oauth2/tokens/revoke",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {get_basic_auth_header()}",
                },
                json={"token": access_token},
            )

        # Delete integration
        db.delete(integration)
        db.commit()

        logger.info(f"✅ QuickBooks disconnected for user: {current_user.email}")

        return {"success": True}

    except Exception as e:
        logger.error(f"QuickBooks disconnect error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to disconnect QuickBooks") from e


@router.get("/settings")
async def get_settings(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get QuickBooks sync settings"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration:
        raise HTTPException(status_code=404, detail="QuickBooks not connected")

    return QuickBooksSyncSettings(
        auto_sync_enabled=integration.auto_sync_enabled,
        sync_invoices=integration.sync_invoices,
        sync_payments=integration.sync_payments,
        sync_customers=integration.sync_customers,
    )


@router.put("/settings")
async def update_settings(
    settings: QuickBooksSyncSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update QuickBooks sync settings"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration:
        raise HTTPException(status_code=404, detail="QuickBooks not connected")

    integration.auto_sync_enabled = settings.auto_sync_enabled
    integration.sync_invoices = settings.sync_invoices
    integration.sync_payments = settings.sync_payments
    integration.sync_customers = settings.sync_customers
    integration.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"✅ QuickBooks settings updated for user: {current_user.email}")

    return {"success": True, "message": "Settings updated successfully"}


@router.post("/sync/customer/{client_id}")
async def sync_customer(
    client_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Sync a specific customer to QuickBooks"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration or not integration.sync_customers:
        raise HTTPException(status_code=400, detail="QuickBooks customer sync not enabled")

    # Get client
    client = (
        db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    )

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        access_token = await refresh_access_token(integration, db)

        # Create customer in QuickBooks
        customer_data = {
            "DisplayName": client.business_name or client.contact_name,
            "PrimaryEmailAddr": {"Address": client.email} if client.email else None,
            "PrimaryPhone": {"FreeFormNumber": client.phone} if client.phone else None,
        }

        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                f"{QUICKBOOKS_API_BASE_URL}/company/{integration.realm_id}/customer",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=customer_data,
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"QuickBooks customer sync failed: {error_detail}")

                # Log failed sync
                sync_log = QuickBooksSyncLog(
                    user_id=current_user.id,
                    integration_id=integration.id,
                    sync_type="customer",
                    entity_type="Client",
                    entity_id=client_id,
                    status="failed",
                    error_message=error_detail,
                )
                db.add(sync_log)
                db.commit()

                raise HTTPException(
                    status_code=400, detail=f"Failed to sync customer: {error_detail}"
                )

            qb_customer = response.json().get("Customer", {})
            qb_customer_id = qb_customer.get("Id")

            # Log successful sync
            sync_log = QuickBooksSyncLog(
                user_id=current_user.id,
                integration_id=integration.id,
                sync_type="customer",
                entity_type="Client",
                entity_id=client_id,
                quickbooks_id=qb_customer_id,
                status="success",
                sync_data={"customer_data": customer_data},
            )
            db.add(sync_log)

            integration.last_customer_sync = datetime.utcnow()
            db.commit()

            logger.info(f"✅ Customer synced to QuickBooks: {client.business_name}")

            return {
                "success": True,
                "quickbooks_id": qb_customer_id,
                "message": "Customer synced successfully",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Customer sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync customer: {str(e)}") from e


@router.post("/sync/invoice/{contract_id}")
async def sync_invoice(
    contract_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Sync a specific invoice to QuickBooks"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration or not integration.sync_invoices:
        raise HTTPException(status_code=400, detail="QuickBooks invoice sync not enabled")

    # Get contract
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get client
    client = db.query(Client).filter(Client.id == contract.client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        access_token = await refresh_access_token(integration, db)

        # First, ensure customer exists in QuickBooks
        # Check if we've synced this customer before
        customer_sync = (
            db.query(QuickBooksSyncLog)
            .filter(
                QuickBooksSyncLog.user_id == current_user.id,
                QuickBooksSyncLog.entity_type == "Client",
                QuickBooksSyncLog.entity_id == client.id,
                QuickBooksSyncLog.status == "success",
            )
            .order_by(QuickBooksSyncLog.created_at.desc())
            .first()
        )

        qb_customer_id = customer_sync.quickbooks_id if customer_sync else None

        # If customer not synced, sync them first
        if not qb_customer_id:
            customer_result = await sync_customer(client.id, current_user, db)
            qb_customer_id = customer_result.get("quickbooks_id")

        # Create invoice in QuickBooks
        invoice_data = {
            "CustomerRef": {"value": qb_customer_id},
            "Line": [
                {
                    "Amount": contract.total_value,
                    "DetailType": "SalesItemLineDetail",
                    "Description": contract.description or contract.title,
                    "SalesItemLineDetail": {"Qty": 1, "UnitPrice": contract.total_value},
                }
            ],
            "DueDate": (
                (contract.start_date + timedelta(days=15)).strftime("%Y-%m-%d")
                if contract.start_date
                else None
            ),
        }

        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                f"{QUICKBOOKS_API_BASE_URL}/company/{integration.realm_id}/invoice",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=invoice_data,
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"QuickBooks invoice sync failed: {error_detail}")

                # Log failed sync
                sync_log = QuickBooksSyncLog(
                    user_id=current_user.id,
                    integration_id=integration.id,
                    sync_type="invoice",
                    entity_type="Contract",
                    entity_id=contract_id,
                    status="failed",
                    error_message=error_detail,
                )
                db.add(sync_log)
                db.commit()

                raise HTTPException(
                    status_code=400, detail=f"Failed to sync invoice: {error_detail}"
                )

            qb_invoice = response.json().get("Invoice", {})
            qb_invoice_id = qb_invoice.get("Id")

            # Log successful sync
            sync_log = QuickBooksSyncLog(
                user_id=current_user.id,
                integration_id=integration.id,
                sync_type="invoice",
                entity_type="Contract",
                entity_id=contract_id,
                quickbooks_id=qb_invoice_id,
                status="success",
                sync_data={"invoice_data": invoice_data},
            )
            db.add(sync_log)

            integration.last_invoice_sync = datetime.utcnow()
            db.commit()

            logger.info(f"✅ Invoice synced to QuickBooks: {contract.title}")

            return {
                "success": True,
                "quickbooks_id": qb_invoice_id,
                "message": "Invoice synced successfully",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invoice sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync invoice: {str(e)}") from e


@router.post("/sync/payment/{contract_id}")
async def sync_payment(
    contract_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Sync payment status to QuickBooks"""
    integration = await get_quickbooks_integration(current_user.id, db)

    if not integration or not integration.sync_payments:
        raise HTTPException(status_code=400, detail="QuickBooks payment sync not enabled")

    # Get contract
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.square_payment_status != "paid":
        raise HTTPException(status_code=400, detail="Contract payment not completed")

    try:
        access_token = await refresh_access_token(integration, db)

        # Get the QuickBooks invoice ID
        invoice_sync = (
            db.query(QuickBooksSyncLog)
            .filter(
                QuickBooksSyncLog.user_id == current_user.id,
                QuickBooksSyncLog.entity_type == "Contract",
                QuickBooksSyncLog.entity_id == contract_id,
                QuickBooksSyncLog.sync_type == "invoice",
                QuickBooksSyncLog.status == "success",
            )
            .order_by(QuickBooksSyncLog.created_at.desc())
            .first()
        )

        if not invoice_sync or not invoice_sync.quickbooks_id:
            raise HTTPException(status_code=400, detail="Invoice not synced to QuickBooks yet")

        # Create payment in QuickBooks
        payment_data = {
            "TotalAmt": contract.total_value,
            "CustomerRef": {
                "value": invoice_sync.sync_data.get("invoice_data", {})
                .get("CustomerRef", {})
                .get("value")
            },
            "Line": [
                {
                    "Amount": contract.total_value,
                    "LinkedTxn": [{"TxnId": invoice_sync.quickbooks_id, "TxnType": "Invoice"}],
                }
            ],
        }

        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                f"{QUICKBOOKS_API_BASE_URL}/company/{integration.realm_id}/payment",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=payment_data,
            )

            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.error(f"QuickBooks payment sync failed: {error_detail}")

                # Log failed sync
                sync_log = QuickBooksSyncLog(
                    user_id=current_user.id,
                    integration_id=integration.id,
                    sync_type="payment",
                    entity_type="Contract",
                    entity_id=contract_id,
                    status="failed",
                    error_message=error_detail,
                )
                db.add(sync_log)
                db.commit()

                raise HTTPException(
                    status_code=400, detail=f"Failed to sync payment: {error_detail}"
                )

            qb_payment = response.json().get("Payment", {})
            qb_payment_id = qb_payment.get("Id")

            # Log successful sync
            sync_log = QuickBooksSyncLog(
                user_id=current_user.id,
                integration_id=integration.id,
                sync_type="payment",
                entity_type="Contract",
                entity_id=contract_id,
                quickbooks_id=qb_payment_id,
                status="success",
                sync_data={"payment_data": payment_data},
            )
            db.add(sync_log)

            integration.last_payment_sync = datetime.utcnow()
            db.commit()

            logger.info(f"✅ Payment synced to QuickBooks for contract: {contract.title}")

            return {
                "success": True,
                "quickbooks_id": qb_payment_id,
                "message": "Payment synced successfully",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync payment: {str(e)}") from e
