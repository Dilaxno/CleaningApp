# Backend Refactoring Progress

## ✅ Completed (Phase 1)

### Infrastructure Setup
- ✅ Created `backend/app/domain/` directory structure
- ✅ Created `backend/app/shared/` directory for utilities
- ✅ Created `backend/app/domain/clients/` subdomain

### Shared Utilities
- ✅ `backend/app/shared/validators.py` - Extracted common validators:
  - `validate_uuid()` - UUID format validation
  - `validate_us_phone()` - US phone number normalization to E.164
  - `validate_email()` - Email format validation
  - `validate_subdomain()` - Subdomain format validation

### Client Domain
- ✅ `backend/app/domain/clients/schemas.py` - Extracted all Pydantic schemas:
  - `ClientCreate` - Create client schema
  - `ClientUpdate` - Update client schema
  - `ClientResponse` - Client response schema
  - `PublicClientCreate` - Public form submission schema
  - `BatchDeleteRequest` - Batch delete schema
  - `BatchDeleteQuoteRequestsRequest` - Quote requests batch delete
  - `QuotePreviewRequest` - Quote preview schema
  - `QuoteAdjustmentRequest` - Quote adjustment schema

### Configuration Updates
- ✅ Updated `backend/pyproject.toml` - Added ruff ignore rule to prevent Pydantic validator issues
- ✅ Fixed `backend/app/routes/subdomain.py` - Added missing `@classmethod` to validator

## 📋 Next Steps (Phases 2-7)

### Phase 2: Complete Client Domain Refactoring
**Estimated Time: 45 minutes**

1. Create `backend/app/domain/clients/repository.py`:
   - Extract all database queries from `clients.py`
   - Methods: `get_clients()`, `get_client_by_id()`, `create_client()`, `update_client()`, `delete_client()`
   - Methods: `get_quote_requests()`, `get_quote_stats()`, `batch_delete()`

2. Create `backend/app/domain/clients/service.py`:
   - Extract business logic from `clients.py`
   - Methods: `validate_client_limit()`, `generate_csv_export()`, `process_quote_approval()`
   - Methods: `calculate_quote_preview()`, `adjust_quote()`, `handle_public_submission()`

3. Create `backend/app/domain/clients/router.py`:
   - Thin FastAPI endpoints that call service layer
   - Move all routes from `backend/app/routes/clients.py`
   - Keep only HTTP concerns (request/response handling)

4. Update `backend/app/main.py`:
   - Import router from `domain.clients` instead of `routes.clients`
   - Test all endpoints still work

5. Archive old file:
   - Rename `backend/app/routes/clients.py` → `backend/app/routes/_archived_clients.py`

### Phase 3: Extract Contracts Domain
**Estimated Time: 45 minutes**

Files to refactor:
- `backend/app/routes/contracts.py` (36KB)
- `backend/app/routes/contracts_pdf.py` (68KB)

Structure:
```
backend/app/domain/contracts/
├── __init__.py
├── schemas.py          # Contract schemas
├── repository.py       # Contract database queries
├── service.py          # Contract business logic
├── pdf_service.py      # PDF generation (from contracts_pdf.py)
└── router.py           # Contract endpoints
```

### Phase 4: Extract Billing Domain
**Estimated Time: 45 minutes**

Files to refactor:
- `backend/app/routes/billing.py` (68KB)

Structure:
```
backend/app/domain/billing/
├── __init__.py
├── schemas.py          # Billing schemas
├── repository.py       # Billing queries
├── stripe_service.py   # Stripe API integration
├── subscription_service.py  # Subscription management
└── router.py           # Billing endpoints
```

### Phase 5: Extract Integrations Domain
**Estimated Time: 30 minutes**

Files to refactor:
- `backend/app/routes/square_webhooks.py` (75KB)
- `backend/app/routes/square.py` (12KB)
- `backend/app/routes/quickbooks.py` (26KB)
- `backend/app/routes/calendly.py` (17KB)
- `backend/app/services/square_service.py` (20KB)
- `backend/app/services/square_subscription.py` (15KB)
- `backend/app/services/square_invoice_automation.py` (12KB)

Structure:
```
backend/app/domain/integrations/
├── __init__.py
├── square/
│   ├── __init__.py
│   ├── schemas.py
│   ├── service.py          # Square API client
│   ├── webhook_handler.py  # Webhook processing
│   ├── subscription.py     # Subscription management
│   ├── invoice_automation.py
│   └── router.py
├── quickbooks/
│   ├── __init__.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
└── calendly/
    ├── __init__.py
    ├── schemas.py
    ├── service.py
    └── router.py
```

### Phase 6: Extract Email Domain
**Estimated Time: 30 minutes**

Files to refactor:
- `backend/app/email_service.py` (93KB)

Structure:
```
backend/app/domain/email/
├── __init__.py
├── schemas.py          # Email template schemas
├── smtp_service.py     # SMTP configuration
├── sender.py           # Email sending logic
└── templates.py        # Template rendering
```

### Phase 7: Extract Scheduling Domain
**Estimated Time: 30 minutes**

Files to refactor:
- `backend/app/routes/scheduling.py` (49KB)
- `backend/app/routes/schedules.py` (32KB)

Structure:
```
backend/app/domain/scheduling/
├── __init__.py
├── schemas.py
├── repository.py
├── service.py
└── router.py
```

### Phase 8: Cleanup & Testing
**Estimated Time: 30 minutes**

1. Move archived files to `backend/app/routes/_archived/`
2. Update all imports across the codebase
3. Run tests: `pytest`
4. Run linters: `make lint`
5. Update documentation
6. Create migration guide for team

## Benefits Achieved So Far

1. **Separation of Concerns**: Validators are now shared utilities
2. **Reusability**: Phone validation used across multiple domains
3. **Testability**: Validators can be tested independently
4. **Type Safety**: All schemas properly typed with Pydantic
5. **Maintainability**: Clear structure for future development

## File Size Reduction Targets

| File | Current Size | Target Size | Strategy |
|------|-------------|-------------|----------|
| `clients.py` | 101KB (2256 lines) | <20KB | Split into 5 files (schemas, repository, service, router, utils) |
| `email_service.py` | 93KB | <25KB | Split into 4 files (smtp, sender, templates, schemas) |
| `square_webhooks.py` | 75KB | <20KB | Split into webhook_handler + service |
| `contracts_pdf.py` | 68KB | <20KB | Extract to pdf_service.py |
| `billing.py` | 68KB | <25KB | Split into stripe_service + subscription_service |

## Total Estimated Time Remaining
- Phase 2: 45 min
- Phase 3: 45 min
- Phase 4: 45 min
- Phase 5: 30 min
- Phase 6: 30 min
- Phase 7: 30 min
- Phase 8: 30 min
**Total: ~4 hours**

## Notes
- Each phase can be done independently
- Tests should be run after each phase
- Keep backward compatibility during migration
- Use feature flags if needed for gradual rollout
