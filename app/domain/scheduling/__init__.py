"""
Scheduling Domain - DEFERRED

This domain handles appointment scheduling, proposals, and booking workflows.

CURRENT STATUS: Deferred to future phase due to high complexity and risk.

CURRENT LOCATION:
- backend/app/routes/schedules.py (801 lines, 8 endpoints)
- backend/app/routes/scheduling.py (1,286 lines, 11 endpoints)

WHY DEFERRED:
1. Complex state machines (client status, schedule approval, proposals)
2. Multiple external integrations (Google Calendar, Square, Calendly)
3. 10+ critical email notifications
4. Public endpoints with custom token security
5. Complex time calculations and availability logic
6. Extensive cross-domain dependencies
7. 2,087 lines of critical business logic
8. High risk of breaking booking workflows

RISK ASSESSMENT: CRITICAL
- Breaking booking workflows would prevent clients from booking services
- Breaking state transitions would disrupt the entire workflow
- Breaking integrations would affect calendar sync and payment processing
- Breaking email notifications would disrupt critical communications
- Breaking public endpoints would prevent client self-service

FUTURE REFACTORING PLAN:

When ready to refactor (requires comprehensive test coverage):

Target Structure:
```
backend/app/domain/scheduling/
├── __init__.py
├── schemas.py              # Schedule, proposal, booking schemas
├── repository.py           # Schedule database queries
├── time_calculator.py      # Time parsing and calculations
├── availability_service.py # Busy slots, working hours
├── proposal_service.py     # Proposal workflow (scheduling.py)
├── approval_service.py     # Approval workflow (schedules.py)
├── integration_service.py  # Google Calendar, Square, Calendly
├── token_service.py        # Token generation and verification
├── router_schedules.py     # Schedule CRUD endpoints
└── router_scheduling.py    # Scheduling workflow endpoints
```

Estimated Time: 4-6 hours (very complex workflows)

Prerequisites:
1. Comprehensive test coverage (unit + integration tests)
2. Staging environment for testing
3. Ability to rollback quickly
4. Dedicated time for thorough testing
5. All external integrations stable

CURRENT ENDPOINTS (Working in original files):

schedules.py (8 endpoints):
- GET /schedules - Get all schedules
- POST /schedules - Create schedule
- PATCH /schedules/{schedule_id} - Update schedule
- DELETE /schedules/{schedule_id} - Delete schedule
- POST /schedules/{schedule_id}/approve - Approve/request change
- GET /schedules/public/proposal/{schedule_id} - View proposal (public)
- POST /schedules/public/proposal/{schedule_id}/accept - Accept proposal (public)
- POST /schedules/public/proposal/{schedule_id}/counter - Counter-propose (public)

scheduling.py (11 endpoints):
- GET /scheduling/info/{client_id} - Get scheduling info (public)
- GET /scheduling/client/{client_id}/latest - Get latest appointment (public)
- POST /scheduling/book - Create booking (public)
- POST /scheduling/proposals - Create proposal
- GET /scheduling/proposals/contract/{contract_id} - Get proposals
- POST /scheduling/proposals/{proposal_id}/accept - Accept slot
- POST /scheduling/proposals/{proposal_id}/counter - Counter-propose
- GET /scheduling/proposals/public/{contract_id} - Get proposals (public)
- GET /scheduling/public/contract/{contract_public_id} - Get contract info (public)
- GET /scheduling/public/busy - Get busy intervals (public)
- POST /scheduling/public/book - Direct booking (public)
- GET /scheduling/busy-slots/{client_id} - Get busy slots (public)

EXTERNAL INTEGRATIONS:
- Google Calendar (create/update/delete events)
- Square (invoice automation on approval)
- Calendly (consultation requirements)

EMAIL NOTIFICATIONS:
- Appointment confirmations (client + provider)
- Schedule change requests
- Proposal notifications
- Counter-proposal notifications
- Pending booking notifications
- Invoice payment links

SECURITY:
- Token-based authentication for public endpoints
- Contract status validation
- Duplicate prevention logic

For more details, see: backend/PHASE_7_EVALUATION.md

Last Updated: 2026-02-16
Status: Deferred ⏸️
Reason: Critical booking workflows with complex state machines
"""
