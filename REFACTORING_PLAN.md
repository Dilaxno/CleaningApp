# Backend Refactoring Plan: Domain-Driven Architecture

## Current Issues
- `clients.py`: 2256 lines (101KB) - Mixed concerns: CRUD, validation, CSV export, contract generation
- `email_service.py`: 93KB - Email templates, sending logic, SMTP configuration
- `square_webhooks.py`: 75KB - Webhook handling, payment processing, subscription management
- `contracts_pdf.py`: 68KB - PDF generation, template rendering, storage
- `billing.py`: 68KB - Stripe integration, subscription management, payment processing

## Target Architecture

```
backend/app/
├── core/                    # Shared infrastructure
│   ├── config.py           # Configuration (existing)
│   ├── database.py         # Database connection (existing)
│   ├── auth.py             # Authentication (existing)
│   ├── dependencies.py     # FastAPI dependencies
│   └── exceptions.py       # Custom exceptions
│
├── domain/                  # Business logic by domain
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── models.py       # Client SQLAlchemy models
│   │   ├── schemas.py      # Pydantic schemas (ClientCreate, ClientUpdate)
│   │   ├── service.py      # Business logic (validation, CRUD operations)
│   │   ├── repository.py   # Database queries
│   │   └── router.py       # FastAPI endpoints
│   │
│   ├── contracts/
│   │   ├── __init__.py
│   │   ├── models.py       # Contract models
│   │   ├── schemas.py      # Contract schemas
│   │   ├── service.py      # Contract business logic
│   │   ├── pdf_service.py  # PDF generation
│   │   ├── repository.py   # Contract queries
│   │   └── router.py       # Contract endpoints
│   │
│   ├── billing/
│   │   ├── __init__.py
│   │   ├── models.py       # Billing models
│   │   ├── schemas.py      # Billing schemas
│   │   ├── stripe_service.py    # Stripe integration
│   │   ├── subscription_service.py  # Subscription logic
│   │   ├── repository.py   # Billing queries
│   │   └── router.py       # Billing endpoints
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── square/
│   │   │   ├── __init__.py
│   │   │   ├── service.py      # Square API client
│   │   │   ├── webhook_handler.py  # Webhook processing
│   │   │   └── router.py       # Square endpoints
│   │   ├── quickbooks/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   └── calendly/
│   │       ├── __init__.py
│   │       ├── service.py
│   │       └── router.py
│   │
│   ├── scheduling/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── router.py
│   │
│   └── email/
│       ├── __init__.py
│       ├── schemas.py      # Email templates
│       ├── smtp_service.py # SMTP configuration
│       ├── sender.py       # Email sending logic
│       └── templates/      # Email template files
│
├── shared/                  # Shared utilities
│   ├── __init__.py
│   ├── validators.py       # Common validators (phone, email, etc.)
│   ├── formatters.py       # Data formatting utilities
│   ├── rate_limiter.py     # Rate limiting (existing)
│   └── security.py         # Security utilities
│
├── models.py               # Legacy models (to be migrated)
└── main.py                 # FastAPI app initialization
```

## Refactoring Strategy

### Phase 1: Create Infrastructure (30 min)
1. Create domain directory structure
2. Create base classes and utilities
3. Set up dependency injection patterns

### Phase 2: Extract Clients Domain (45 min)
1. Extract schemas from clients.py → domain/clients/schemas.py
2. Extract business logic → domain/clients/service.py
3. Extract database queries → domain/clients/repository.py
4. Create thin router → domain/clients/router.py
5. Update imports in main.py

### Phase 3: Extract Contracts Domain (45 min)
1. Split contracts.py and contracts_pdf.py
2. Separate PDF generation logic
3. Create contract service layer

### Phase 4: Extract Billing Domain (45 min)
1. Split billing.py into service layers
2. Separate Stripe integration
3. Extract subscription management

### Phase 5: Extract Integrations (30 min)
1. Organize Square, QuickBooks, Calendly
2. Standardize webhook handling
3. Create integration base classes

### Phase 6: Extract Email Domain (30 min)
1. Split email_service.py
2. Separate SMTP configuration
3. Extract template rendering

### Phase 7: Cleanup & Testing (30 min)
1. Remove old files
2. Update all imports
3. Run tests
4. Update documentation

## Benefits
- **Single Responsibility**: Each module has one clear purpose
- **Testability**: Easy to mock dependencies and test in isolation
- **Maintainability**: Changes are localized to specific domains
- **Scalability**: Easy to add new features within domains
- **Team Collaboration**: Multiple developers can work on different domains

## Migration Notes
- Keep backward compatibility during migration
- Use feature flags if needed
- Migrate one domain at a time
- Update tests incrementally
