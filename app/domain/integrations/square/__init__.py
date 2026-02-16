"""Square integration - Payment processing and invoicing"""

# Note: Square integration is kept in original files for now:
# - backend/app/routes/square.py - OAuth and connection management
# - backend/app/routes/square_webhooks.py - Webhook handlers
# - backend/app/services/square_service.py - Square API client
# - backend/app/services/square_subscription.py - Subscription management
# - backend/app/services/square_invoice_automation.py - Invoice automation
#
# These will be refactored in a future phase due to:
# - Complex OAuth flow with state management
# - Webhook signature verification
# - Real-time payment processing
# - Invoice automation workflows

__all__ = []
