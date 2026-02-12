# Custom Quote Workflow Implementation Guide

## Overview
This document outlines the complete custom quote workflow from client request to payment confirmation.

## Workflow Steps

### 1. Client Receives Automatic Quote
**Location:** Client form after submitting property details

**UI Changes Needed:**
- Show two buttons instead of one:
  - "Approve & Schedule" (primary, teal) → Goes to scheduling
  - "Need Custom Quote" (secondary, outline) → Opens custom quote request modal

### 2. Custom Quote Request Submission
**When client clicks "Need Custom Quote":**

**Modal Content:**
- Title: "Request Custom Quote"
- Text area: "Tell us more about your specific needs..."
- Optional: Video upload for property walkthrough
- Submit button: "Submit Request"

**Backend Endpoint:** `POST /clients/{client_id}/custom-quote-request`

**Request Body:**
```json
{
  "notes": "I need extra attention to...",
  "video_r2_key": "optional_video_key"
}
```

**Response:**
```json
{
  "success": true,
  "request_id": 123,
  "status": "pending"
}
```

### 3. Waiting Screen
**After submission, show:**
- Illustration: Waiting animation
- Title: "Waiting for [Business Name]..."
- Message: "We'll email your custom quote after the provider reviews your request."
- Subtext: "This usually takes 1-2 business days"
- Button: "Return to Home"

### 4. Provider Dashboard - Custom Quote Requests Page
**New Page:** `/dashboard/custom-quotes`

**Features:**
- List all pending custom quote requests
- Show client info, property details, notes, video (if uploaded)
- "Review & Quote" button for each request

**Quote Form:**
- Amount field
- Description text area
- Line items (optional):
  - Item name
  - Quantity
  - Unit price
- Provider notes to client
- Expiration date (optional)
- "Send Quote" button

**Backend Endpoint:** `POST /custom-quote-requests/{request_id}/quote`

**Request Body:**
```json
{
  "amount": 250.00,
  "description": "Custom deep cleaning package",
  "line_items": [
    {
      "name": "Deep cleaning",
      "quantity": 1,
      "unit_price": 200.00
    },
    {
      "name": "Carpet cleaning",
      "quantity": 2,
      "unit_price": 25.00
    }
  ],
  "notes": "This includes all areas you mentioned...",
  "expires_at": "2026-03-15T00:00:00Z"
}
```

### 5. Email Client with Custom Quote
**Triggered automatically when provider submits quote**

**Email Content:**
- Subject: "Your Custom Quote from [Business Name]"
- Header: "Your Custom Quote is Ready! 📋"
- Quote details:
  - Total amount
  - Description
  - Line items breakdown
  - Provider notes
  - Expiration date
- CTA Button: "Approve & Schedule" → Links to scheduling flow
- Secondary link: "View Full Details"

**Email Link:** `https://domain.com/quote/{public_id}/approve`

### 6. Client Approves Quote & Schedules
**When client clicks "Approve & Schedule":**

**Flow:**
1. Show quote summary
2. "Confirm Quote" button
3. Redirect to scheduling page (existing flow)
4. After scheduling, show contract signing page
5. Client signs contract

**Backend Updates:**
- Update custom quote request status to "approved"
- Create contract with custom quote amount
- Link contract to custom quote request

### 7. Provider Reviews Schedule & Signs
**Provider Dashboard Notification:**
- Badge on "Schedules" or "Contracts" page
- "Pending Your Signature" section
- Show client's selected time
- Options:
  - "Accept & Sign" → Signs contract
  - "Propose Different Time" → Opens time proposal modal

**After Provider Signs:**
- Contract status → "signed" (both parties signed)
- If Square connected → Automatically create and send invoice

### 8. Square Invoice Automation
**Triggered when provider signs contract**

**Conditions:**
- Square integration is active
- Contract has both signatures
- No invoice created yet

**Action:**
```python
# Create Square invoice
invoice = create_square_invoice(
    contract=contract,
    client=client,
    amount=contract.total_value
)

# Send invoice to client
send_square_invoice(invoice_id)

# Update contract
contract.square_invoice_id = invoice.id
contract.square_invoice_url = invoice.public_url
```

**Email to Client:**
- Subject: "Invoice Ready - [Service Name]"
- Content: "Your service is confirmed! Please complete payment."
- CTA: "Pay Invoice" → Square payment page

### 9. Payment Webhook Confirmation
**When Square webhook receives `payment.updated` with `status == "COMPLETED"`:**

**Actions:**
1. Update contract payment status
2. Send confirmation emails
3. Set payment_confirmation_pending flag
4. Create subscription (if recurring)

### 10. Payment Confirmation Page
**URL:** `/payment-confirmation?contract_id={id}`

**Enhanced Content:**
- Success animation
- Booking details:
  - Service name
  - Scheduled date/time
  - Service address
  - Provider contact info
  - Total amount paid
- "Download Contract" button
- "Add to Calendar" button
- Next steps section

**Download Contract Endpoint:** `GET /contracts/{contract_id}/download`

**Response:** PDF file with signed contract

## Database Schema Updates

### CustomQuoteRequest Table (Already Exists)
```sql
-- Add any missing fields
ALTER TABLE custom_quote_requests 
ADD COLUMN IF NOT EXISTS client_notes TEXT;

ALTER TABLE custom_quote_requests 
ADD COLUMN IF NOT EXISTS provider_viewed_at TIMESTAMP;
```

### Contract Table Updates
```sql
-- Link to custom quote request
ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS custom_quote_request_id INTEGER REFERENCES custom_quote_requests(id);

-- Track invoice automation
ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS invoice_auto_sent BOOLEAN DEFAULT FALSE;

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS invoice_auto_sent_at TIMESTAMP;
```

## API Endpoints Summary

### Client Endpoints (Public)
1. `POST /clients/{client_id}/custom-quote-request` - Submit custom quote request
2. `GET /custom-quote-requests/{public_id}` - View quote details
3. `POST /custom-quote-requests/{public_id}/approve` - Approve quote
4. `GET /contracts/{contract_id}/download` - Download signed contract

### Provider Endpoints (Authenticated)
1. `GET /custom-quote-requests` - List all requests
2. `GET /custom-quote-requests/{id}` - Get request details
3. `POST /custom-quote-requests/{id}/quote` - Submit custom quote
4. `PUT /custom-quote-requests/{id}/status` - Update status
5. `POST /contracts/{id}/auto-invoice` - Manually trigger invoice (if needed)

### Webhook Endpoints
1. `POST /webhooks/square/payment` - Handle payment updates (already exists)

## Frontend Components Needed

### Client Side
1. `QuoteApprovalButtons.tsx` - Two button component
2. `CustomQuoteRequestModal.tsx` - Request submission modal
3. `CustomQuoteWaitingScreen.tsx` - Waiting state
4. `QuoteApprovalPage.tsx` - Quote review and approval
5. `PaymentConfirmationEnhanced.tsx` - Enhanced confirmation with booking details

### Provider Side
1. `CustomQuoteRequestsList.tsx` - List of pending requests
2. `CustomQuoteRequestDetail.tsx` - Single request view
3. `CustomQuoteForm.tsx` - Quote submission form
4. `ScheduleApprovalCard.tsx` - Pending schedule approval UI

## Email Templates

### 1. Custom Quote Request Notification (to Provider)
```
Subject: New Custom Quote Request from [Client Name]

Hi [Provider Name],

[Client Name] has requested a custom quote for their cleaning service.

Property Details:
- Type: [property_type]
- Size: [size] sqft
- Frequency: [frequency]

Client Notes:
[client_notes]

[View Video] (if uploaded)

[Review & Send Quote Button]
```

### 2. Custom Quote Ready (to Client)
```
Subject: Your Custom Quote from [Business Name]

Hi [Client Name],

Great news! Your custom quote is ready.

Service: [service_name]
Total: $[amount]

[Line items breakdown]

Provider Notes:
[provider_notes]

This quote expires on [expiration_date]

[Approve & Schedule Button]
```

### 3. Schedule Pending Approval (to Provider)
```
Subject: Schedule Approval Needed - [Client Name]

Hi [Provider Name],

[Client Name] has selected their preferred time:

Date: [date]
Time: [start_time] - [end_time]

[Accept & Sign Button]
[Propose Different Time Button]
```

### 4. Invoice Ready (to Client)
```
Subject: Invoice Ready - [Service Name]

Hi [Client Name],

Your service is confirmed! Please complete payment to finalize your booking.

Service: [service_name]
Amount: $[amount]
Due: [due_date]

[Pay Invoice Button]
```

### 5. Payment Confirmed (to Both)
```
Subject: Payment Confirmed - Booking Complete

Your payment has been received and your booking is confirmed!

Booking Details:
- Service: [service_name]
- Date: [date]
- Time: [time]
- Address: [address]

[Download Contract Button]
[Add to Calendar Button]
```

## Implementation Priority

### Phase 1 (Core Flow)
1. ✅ Payment webhook (already done)
2. Custom quote request submission
3. Provider quote form
4. Email notifications
5. Quote approval flow

### Phase 2 (Enhancements)
1. Schedule approval workflow
2. Square invoice automation
3. Enhanced confirmation page
4. Contract download

### Phase 3 (Polish)
1. Video upload for custom quotes
2. Calendar integration
3. SMS notifications
4. Analytics dashboard

## Testing Checklist

- [ ] Client can submit custom quote request
- [ ] Provider receives email notification
- [ ] Provider can view request details
- [ ] Provider can submit custom quote
- [ ] Client receives quote email
- [ ] Client can approve quote
- [ ] Client can schedule after approval
- [ ] Client can sign contract
- [ ] Provider receives schedule notification
- [ ] Provider can sign contract
- [ ] Square invoice is auto-created
- [ ] Client receives invoice email
- [ ] Payment webhook updates status
- [ ] Confirmation page shows booking details
- [ ] Contract download works
- [ ] All emails are sent correctly

## Configuration

### Environment Variables
```bash
# Square (already configured)
SQUARE_APPLICATION_ID=
SQUARE_APPLICATION_SECRET=
SQUARE_WEBHOOK_SIGNATURE_KEY=

# Email service
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=

# Frontend URL
FRONTEND_URL=https://yourdomain.com
```

### Feature Flags
```python
# In business config
enable_custom_quotes = True
enable_auto_invoicing = True
require_schedule_approval = True
```

## Notes

- Custom quote requests expire after 30 days by default
- Providers can set custom expiration dates
- Video uploads are optional but recommended
- Square invoice is only sent if integration is active
- Payment confirmation page is accessible via public link
- Contract download requires authentication or public_id
