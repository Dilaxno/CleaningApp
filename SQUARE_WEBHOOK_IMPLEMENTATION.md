# Square Payment Webhook Implementation

## Overview
This implementation handles Square's `payment.updated` webhook events to automatically process payments, update invoice statuses, send confirmation emails, and trigger frontend redirects.

## Architecture

### 1. Webhook Endpoint
**Location:** `backend/app/routes/square_webhooks.py`

**Endpoint:** `POST /webhooks/square/payment`

**Features:**
- Signature verification using HMAC-SHA256
- Event type filtering
- Handles `payment.updated`, `payment.created`, and `invoice.payment_made` events

### 2. Payment Processing Flow

#### Step 1: Webhook Receives Event
```
Square → POST /webhooks/square/payment
```

#### Step 2: Verification
- Verifies webhook signature using `SQUARE_WEBHOOK_SIGNATURE_KEY`
- Validates event type and payment status
- Only processes when:
  - `event_type == "payment.updated"`
  - `payment.status == "COMPLETED"`

#### Step 3: Database Update
When both conditions are met:
- Updates `contract.square_payment_status = "paid"`
- Sets `contract.square_payment_received_at = datetime.utcnow()`
- Updates `contract.status = "active"` (if currently "signed")
- Sets `contract.payment_confirmation_pending = True` (for frontend redirect)
- Sets `contract.payment_confirmed_at = datetime.utcnow()`

#### Step 4: Email Notifications
Automatically sends two emails:

**A. Service Provider Email:**
- Subject: "💰 Payment Received - $XX.XX from [Client Name]"
- Contains:
  - Invoice number
  - Client name, email, phone
  - Service details
  - Amount paid
  - Payment date and ID
  - Link to contract details

**B. Client Email:**
- Subject: "✅ Payment Received - [Service Title]"
- Contains:
  - Payment confirmation
  - Invoice details
  - Service information
  - Next steps
  - Subscription info (if recurring)

#### Step 5: Subscription Creation (if applicable)
For recurring services:
- Creates Square subscription automatically
- Sends subscription confirmation to client
- Sends subscription notification to provider

### 3. Frontend Redirect Flow

#### Polling Mechanism
The frontend can poll the payment status endpoint to detect when payment is confirmed:

**Endpoint:** `GET /webhooks/square/payment-status/{contract_id}`

**Response:**
```json
{
  "payment_confirmed": true,
  "confirmed_at": "2026-02-12T19:40:37.000Z",
  "redirect_url": "/payment-confirmation?contract_id=123",
  "contract_id": 123,
  "amount": 150.00
}
```

#### Frontend Implementation
```typescript
// Poll every 3 seconds after payment submission
const checkPaymentStatus = async (contractId: number) => {
  const response = await fetch(
    `${API_URL}/webhooks/square/payment-status/${contractId}`
  );
  const data = await response.json();
  
  if (data.payment_confirmed && data.redirect_url) {
    // Redirect to confirmation page
    window.location.href = data.redirect_url;
  }
};
```

### 4. Payment Confirmation Page
**Location:** `frontend/src/pages/Payment/PaymentConfirmation.tsx`

**Features:**
- Success animation with checkmark
- Payment amount display
- Confirmation checklist
- Next steps information
- Automatic status checking

**URL:** `/payment-confirmation?contract_id={id}`

## Database Schema

### New Fields Added to `contracts` Table

```sql
ALTER TABLE contracts 
ADD COLUMN payment_confirmation_pending BOOLEAN DEFAULT FALSE;

ALTER TABLE contracts 
ADD COLUMN payment_confirmed_at TIMESTAMP;
```

**Fields:**
- `payment_confirmation_pending`: Flag to trigger frontend redirect
- `payment_confirmed_at`: Timestamp when webhook confirmed payment

## Configuration

### Environment Variables Required

```bash
# Square Webhook Signature Key (from Square Dashboard)
SQUARE_WEBHOOK_SIGNATURE_KEY=your_signature_key_here

# Frontend URL for email links
FRONTEND_URL=https://yourdomain.com
```

### Square Dashboard Setup

1. Go to Square Developer Dashboard
2. Navigate to Webhooks
3. Create new webhook subscription
4. Subscribe to events:
   - `payment.updated`
   - `payment.created`
   - `invoice.payment_made`
5. Set webhook URL: `https://yourdomain.com/webhooks/square/payment`
6. Copy the Signature Key to your `.env` file

## Security

### Signature Verification
All webhook requests are verified using HMAC-SHA256:

```python
message = notification_url + request_body
signature = HMAC-SHA256(SQUARE_WEBHOOK_SIGNATURE_KEY, message)
```

### Protection Against
- Replay attacks (signature verification)
- Unauthorized requests (signature validation)
- Data tampering (HMAC integrity check)

## Email Templates

### Provider Notification Email
- Green gradient header with "💰 Payment Received!"
- Detailed invoice table
- Client contact information
- Payment status indicators
- Link to contract details
- Recurring service indicator (if applicable)

### Client Confirmation Email
- Teal gradient header with "✅ Payment Received"
- Payment details table
- Service information
- What's next section
- Subscription details (if recurring)

## Testing

### Test Webhook Locally

```bash
# Use Square's webhook testing tool or curl
curl -X POST http://localhost:8000/webhooks/square/payment \
  -H "Content-Type: application/json" \
  -H "x-square-hmacsha256-signature: YOUR_SIGNATURE" \
  -d '{
    "type": "payment.updated",
    "data": {
      "object": {
        "payment": {
          "id": "test_payment_123",
          "status": "COMPLETED",
          "invoice_id": "inv_123"
        }
      }
    }
  }'
```

### Test Payment Status Endpoint

```bash
curl http://localhost:8000/webhooks/square/payment-status/123
```

## Error Handling

### Webhook Failures
- Invalid signature → 401 Unauthorized
- Invalid JSON → 400 Bad Request
- Processing error → 500 Internal Server Error
- All errors logged with detailed context

### Email Failures
- Logged but don't block webhook processing
- Payment still marked as confirmed
- Provider can manually resend if needed

### Database Failures
- Transaction rollback on error
- Webhook returns error to Square for retry
- Square will retry failed webhooks automatically

## Monitoring

### Log Messages
- `📥 Received Square webhook: {event_type}`
- `💳 Payment event: {payment_id} - Status: {status}`
- `✅ Contract {id} payment status updated: {old} → {new}`
- `✅ Payment confirmation state stored for frontend redirect`
- `✅ Provider payment notification sent to {email}`
- `✅ Payment confirmation emails sent for contract {id}`

### Key Metrics to Monitor
- Webhook success rate
- Email delivery rate
- Average processing time
- Failed signature verifications
- Payment confirmation lag time

## Troubleshooting

### Webhook Not Receiving Events
1. Check Square Dashboard webhook status
2. Verify webhook URL is publicly accessible
3. Check firewall/security group settings
4. Verify SSL certificate is valid

### Signature Verification Failing
1. Verify `SQUARE_WEBHOOK_SIGNATURE_KEY` is correct
2. Check that notification URL matches exactly
3. Ensure no middleware is modifying request body

### Emails Not Sending
1. Check email service configuration
2. Verify SMTP credentials
3. Check spam folders
4. Review email service logs

### Frontend Not Redirecting
1. Verify `payment_confirmation_pending` flag is set
2. Check frontend polling interval
3. Verify contract ID is correct
4. Check browser console for errors

## Future Enhancements

### Potential Improvements
1. Add webhook event history table
2. Implement idempotency keys
3. Add webhook retry mechanism
4. Create admin dashboard for webhook monitoring
5. Add SMS notifications option
6. Implement webhook event replay for debugging
7. Add support for partial payments
8. Create webhook event analytics

## API Reference

### POST /webhooks/square/payment
Handles Square webhook events for payments.

**Headers:**
- `x-square-hmacsha256-signature`: HMAC signature for verification

**Body:**
```json
{
  "type": "payment.updated",
  "data": {
    "object": {
      "payment": {
        "id": "payment_id",
        "status": "COMPLETED",
        "invoice_id": "invoice_id",
        "order_id": "order_id"
      }
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "event_type": "payment.updated"
}
```

### GET /webhooks/square/payment-status/{contract_id}
Check payment confirmation status for frontend redirect.

**Parameters:**
- `contract_id`: Contract ID to check

**Response:**
```json
{
  "payment_confirmed": true,
  "confirmed_at": "2026-02-12T19:40:37.000Z",
  "redirect_url": "/payment-confirmation?contract_id=123",
  "contract_id": 123,
  "amount": 150.00
}
```

## Support

For issues or questions:
1. Check logs in `backend/app/routes/square_webhooks.py`
2. Review Square Developer Dashboard webhook logs
3. Test webhook signature verification
4. Verify database schema is up to date
5. Check email service status

## Migration

To apply the database changes:

```bash
cd backend
python run_migration.py migrations/add_payment_confirmation_fields.sql
```

Or manually:
```bash
psql -U your_user -d your_database -f migrations/add_payment_confirmation_fields.sql
```
