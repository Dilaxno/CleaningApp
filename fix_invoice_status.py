"""
Script to manually mark invoices as paid
Use this when webhook fails or for offline payments
"""
import sys
from datetime import datetime
from app.database import SessionLocal
from app.models_invoice import Invoice
from app.models import User

def mark_invoice_paid(invoice_id: int, payment_reference: str = None):
    """Manually mark an invoice as paid"""
    db = SessionLocal()
    
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            print(f"❌ Invoice {invoice_id} not found")
            return False
        
        if invoice.status == "paid":
            print(f"ℹ️  Invoice {invoice.invoice_number} is already marked as paid")
            print(f"   Paid at: {invoice.paid_at}")
            return True
        
        # Get user info
        user = db.query(User).filter(User.id == invoice.user_id).first()
        
        print(f"📋 Invoice Details:")
        print(f"   Invoice #: {invoice.invoice_number}")
        print(f"   Current Status: {invoice.status}")
        print(f"   Amount: ${invoice.total_amount}")
        print(f"   Provider: {user.full_name if user else 'Unknown'} (ID: {invoice.user_id})")
        
        # Confirm
        confirm = input(f"\n⚠️  Mark this invoice as PAID? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return False
        
        # Update invoice
        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow()
        invoice.dodo_payment_id = payment_reference or f"manual-{datetime.utcnow().timestamp()}"
        
        db.commit()
        
        print(f"✅ Invoice {invoice.invoice_number} marked as PAID")
        print(f"   Paid at: {invoice.paid_at}")
        print(f"   Payment ID: {invoice.dodo_payment_id}")
        print(f"\n💡 This invoice will now appear in the 'Available for Payout' section")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def mark_multiple_invoices_paid(invoice_ids: list):
    """Mark multiple invoices as paid"""
    print(f"📋 Marking {len(invoice_ids)} invoices as paid...\n")
    
    success_count = 0
    for invoice_id in invoice_ids:
        if mark_invoice_paid(invoice_id):
            success_count += 1
        print()  # Blank line between invoices
    
    print(f"\n✅ Successfully marked {success_count}/{len(invoice_ids)} invoices as paid")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single invoice:   python fix_invoice_status.py <invoice_id> [payment_reference]")
        print("  Multiple invoices: python fix_invoice_status.py <id1> <id2> <id3> ...")
        print("\nExamples:")
        print("  python fix_invoice_status.py 123")
        print("  python fix_invoice_status.py 123 'check-#4567'")
        print("  python fix_invoice_status.py 123 124 125")
        sys.exit(1)
    
    invoice_ids = [int(id) for id in sys.argv[1:] if id.isdigit()]
    
    if not invoice_ids:
        print("❌ No valid invoice IDs provided")
        sys.exit(1)
    
    if len(invoice_ids) == 1:
        # Single invoice with optional payment reference
        payment_ref = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].isdigit() else None
        mark_invoice_paid(invoice_ids[0], payment_ref)
    else:
        # Multiple invoices
        mark_multiple_invoices_paid(invoice_ids)
