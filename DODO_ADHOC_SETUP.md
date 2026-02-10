# Dodo Payments Adhoc Product Setup

## Overview
Instead of creating individual products for each client invoice (which would create millions of products), we use a single "adhoc" product with "pay what you want" functionality enabled.

## Configuration

### Environment Variable
Add this to your `.env` file:

```bash
# Dodo Payments Adhoc Product ID (pay-what-you-want enabled)
DODO_ADHOC_PRODUCT_ID=pdt_0NWQgv8RX3EG0c34ObKdo
```

### Adhoc Product Requirements
The adhoc product must have:
1. **Pay What You Want** enabled
2. **One-time payment** type
3. Generic name like "Service Payment" or "Invoice Payment"
4. Generic description

## How It Works

1. **Invoice Creation**: Invoices are created normally with amount and details
2. **Payment Link Generation**: Uses the adhoc product with `custom_amount` set to invoice total
3. **Checkout**: Client sees the correct amount and invoice details in metadata
4. **Webhook Processing**: Payment webhook includes invoice details in metadata for processing

## Benefits

- ✅ **Scalable**: No product limit concerns
- ✅ **Clean**: Single product for all payments
- ✅ **Flexible**: Supports any amount via pay-what-you-want
- ✅ **Efficient**: No API calls to create/delete products
- ✅ **Maintainable**: Simpler codebase

## Migration

If you have existing dynamic products, run the cleanup script:

```bash
cd backend
python cleanup_dodo_products.py
```

This will:
1. Delete old dynamic products from Dodo
2. Update existing invoices to reference the adhoc product
3. Preserve all payment links and functionality

## Testing

1. Create an invoice
2. Generate payment link
3. Verify the checkout shows correct amount
4. Complete test payment
5. Confirm webhook processes correctly with invoice metadata