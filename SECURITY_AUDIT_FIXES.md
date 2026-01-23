# Security Audit Fixes - January 2026

## Critical Vulnerabilities Fixed

### 1. JWT Token Signature Verification (CRITICAL)
**File:** `backend/app/auth.py`
**Issue:** Firebase tokens were decoded but NOT cryptographically verified
**Fix:** Added full RSA signature verification using Google's public keys

### 2. Insecure Default SECRET_KEY (HIGH)
**File:** `backend/app/config.py`
**Issue:** Default secret key was hardcoded
**Fix:** Now raises warning if SECRET_KEY not set in environment

### 3. Input Validation - Path Traversal Prevention (HIGH)
**Files:** `routes/upload.py`, `routes/users.py`, `routes/business.py`
**Issue:** firebase_uid parameters not validated, allowing potential injection
**Fix:** Added validation for all path parameters (alphanumeric, max length)

### 4. Missing Rate Limiting on Public Endpoints (MEDIUM)
**Files:** `routes/trial.py`, `routes/clients.py`
**Issue:** Public endpoints vulnerable to abuse/DOS
**Fix:** Added rate limiting (3/hr trial, 10/hr signing)

### 5. File Upload Security (MEDIUM)
**File:** `routes/upload.py`
**Issue:** Filename not validated for path traversal
**Fix:** Added filename sanitization and validation

### 6. User Endpoint Authentication (HIGH) - FIXED
**File:** `routes/users.py`
**Issue:** User endpoints allowed access to any user's data without authentication
**Fix:** Added `get_current_user` authentication to all user endpoints:
- `GET /users/{firebase_uid}` - Now requires auth, users can only access own data
- `GET /users/{firebase_uid}/plan-usage` - Now requires auth
- `PUT /users/{firebase_uid}` - Now requires auth, users can only update own data
- `PATCH /users/{firebase_uid}` - Now requires auth

## Recommendations for Future Work

1. ~~Add authentication to user endpoints (`/users/{firebase_uid}`)~~ ✅ DONE
2. ~~Use UUIDs instead of sequential IDs for public invoice access~~ ✅ DONE
3. ~~Use UUIDs for contract/client public access~~ ✅ DONE
4. ~~Add CSRF protection for state-changing operations~~ ✅ DONE
5. ~~Implement request signing for webhook endpoints~~ ✅ DONE
6. ~~Add security headers middleware (CSP, X-Frame-Options, etc.)~~ ✅ DONE

## All Security Recommendations Completed! ✅

---

### 7. Invoice Enumeration Prevention (MEDIUM) - FIXED
**Files:** `models_invoice.py`, `routes/invoices.py`
**Issue:** Public invoice endpoint used sequential integer IDs, allowing attackers to enumerate all invoices
**Fix:** 
- Added `public_id` UUID column to Invoice model
- Changed `/invoices/public/{invoice_id}` to `/invoices/public/{public_id}` (UUID)
- Added UUID validation to prevent injection
- Created migration script: `add_invoice_public_id.py`

**Migration Required:** Run `python add_invoice_public_id.py` to add UUIDs to existing invoices.

---

### 8. Contract & Client Enumeration Prevention (MEDIUM) - FIXED
**Files:** `models.py`, `routes/contracts.py`, `routes/clients.py`
**Issue:** Public contract signing endpoint used sequential client IDs, allowing attackers to enumerate clients and sign contracts for arbitrary clients
**Fix:**
- Added `public_id` UUID column to Client model
- Added `public_id` UUID column to Contract model
- Changed `/clients/public/sign-contract` to use `clientPublicId` (UUID) instead of `clientId`
- All contract responses now include `public_id` and `clientPublicId`
- Added UUID validation to prevent injection
- Created migration script: `add_contract_client_public_ids.py`

**Migration Required:** Run `python add_contract_client_public_ids.py` to add UUIDs to existing contracts and clients.

---

### 9. CSRF Protection (MEDIUM) - FIXED
**Files:** `csrf.py`, `main.py`
**Issue:** No CSRF protection for state-changing operations, allowing cross-site request forgery attacks
**Fix:** Implemented double-submit cookie pattern:
- Created `CSRFMiddleware` that validates CSRF tokens on POST/PUT/PATCH/DELETE requests
- Added `/csrf-token` endpoint for frontend to obtain tokens
- Token is set as a cookie (`csrf_token`) and must be sent in `X-CSRF-Token` header
- Exempt paths: webhooks, public endpoints (already protected by rate limiting + captcha)
- Can be disabled for development with `CSRF_ENABLED=false` env var

**Frontend Integration Required:**
```javascript
// On app load, get CSRF token
const response = await fetch('/csrf-token', { credentials: 'include' });
const { csrf_token } = await response.json();

// Include in all state-changing requests
fetch('/api/endpoint', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'X-CSRF-Token': csrf_token,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(data),
});
```

---

### 10. Webhook Security Hardening (MEDIUM) - FIXED
**Files:** `webhook_security.py`, `routes/billing.py`, `routes/calendly_webhooks.py`
**Issue:** Webhook signature verification was implemented inline with potential inconsistencies
**Fix:** Created centralized webhook security module with:
- `webhook_security.py` - Centralized signature verification utilities
- Constant-time signature comparison (prevents timing attacks)
- Timestamp validation (prevents replay attacks - 5 minute window)
- Support for multiple providers (Dodo, Calendly, Stripe-ready)
- Detailed security logging for audit trails
- Updated Dodo Payments webhook to use centralized verification
- Updated Calendly webhook to use centralized verification

**Security Features:**
```python
# Constant-time comparison prevents timing attacks
hmac.compare_digest(expected, actual)

# Timestamp validation prevents replay attacks
MAX_WEBHOOK_AGE_SECONDS = 300  # 5 minutes

# Provider-specific verification functions
verify_dodo_webhook(request, secret)
verify_calendly_webhook(request, secret)
verify_stripe_webhook(request, secret)  # Ready for future use
```

---

### 11. Security Headers Middleware (MEDIUM) - FIXED
**Files:** `security_headers.py`, `main.py`
**Issue:** No security headers to protect against common web vulnerabilities
**Fix:** Created `SecurityHeadersMiddleware` that adds comprehensive security headers:

**Headers Added:**
| Header | Value | Protection |
|--------|-------|------------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer leakage |
| `Content-Security-Policy` | Restrictive policy | Prevents XSS, injection |
| `Strict-Transport-Security` | `max-age=31536000` | Enforces HTTPS (prod only) |
| `Permissions-Policy` | Disable unused features | Reduces attack surface |
| `Cache-Control` | `no-store` | Prevents caching sensitive data |
| `Cross-Origin-Opener-Policy` | `same-origin` | Isolates browsing context |
| `Cross-Origin-Resource-Policy` | `same-origin` | Restricts resource sharing |

**Configuration:**
- Can be disabled for development with `SECURITY_HEADERS_ENABLED=false`
- HSTS only enabled in production (`ENVIRONMENT=production`)
- Excludes `/health`, `/docs`, `/openapi.json` paths
