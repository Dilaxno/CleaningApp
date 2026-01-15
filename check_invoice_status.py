"""
Diagnostic script to check invoice payment status
Run this to debug why paid invoices aren't showing up in payouts
"""
import sys
from app.database import SessionLocal
from app.models_invoice import Invoice
from app.models import User
from sqlalchemy import func

def check_invoice_status(user_email: str = None):
    """Check invoice status for a specific user or all users"""
    db = SessionLocal()
    
    try:
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                print(f"❌ User not found: {user_email}")
                return
            user_id = user.id
            print(f"✅ Found user: {user.full_name} (ID: {user_id})")
        else:
            user_id = None
            print("📊 Checking all invoices...")
        
        # Query invoices
        query = db.query(Invoice)
        if user_id:
            query = query.filter(Invoice.user_id == user_id)
        
        invoices = query.order_by(Invoice.created_at.desc()).limit(20).all()
        
        print(f"\n📋 Recent Invoices (showing last 20):")
        print("-" * 120)
        print(f"{'ID':<6} {'Invoice #':<20} {'Status':<12} {'Amount':<12} {'Paid At':<25} {'Payment ID':<30}")
        print("-" * 120)
        
        for inv in invoices:
            paid_at_str = inv.paid_at.strftime("%Y-%m-%d %H:%M:%S") if inv.paid_at else "Not paid"
            payment_id = inv.dodo_payment_id or "None"
            print(f"{inv.id:<6} {inv.invoice_number:<20} {inv.status:<12} ${inv.total_amount:<11.2f} {paid_at_str:<25} {payment_id:<30}")
        
        # Summary statistics
        print("\n📊 Summary Statistics:")
        print("-" * 60)
        
        status_counts = db.query(
            Invoice.status,
            func.count(Invoice.id).label('count'),
            func.sum(Invoice.total_amount).label('total')
        )
        if user_id:
            status_counts = status_counts.filter(Invoice.user_id == user_id)
        
        status_counts = status_counts.group_by(Invoice.status).all()
        
        for status, count, total in status_counts:
            total_amount = total or 0
            print(f"{status.upper():<12} Count: {count:<5} Total: ${total_amount:,.2f}")
        
        # Check for stuck invoices (sent but not paid for > 24 hours)
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        stuck_query = db.query(Invoice).filter(
            Invoice.status == "sent",
            Invoice.created_at < cutoff
        )
        if user_id:
            stuck_query = stuck_query.filter(Invoice.user_id == user_id)
        
        stuck_count = stuck_query.count()
        
        if stuck_count > 0:
            print(f"\n⚠️  WARNING: {stuck_count} invoices stuck in 'sent' status for > 24 hours")
            print("These may have been paid but webhook didn't process correctly.")
            print("\nStuck Invoices:")
            for inv in stuck_query.limit(10).all():
                hours_stuck = (datetime.utcnow() - inv.created_at).total_seconds() / 3600
                print(f"  - Invoice #{inv.invoice_number} (ID: {inv.id}) - Stuck for {hours_stuck:.1f} hours")
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        email = sys.argv[1]
        check_invoice_status(email)
    else:
        print("Usage: python check_invoice_status.py [user_email]")
        print("Example: python check_invoice_status.py provider@example.com")
        print("\nOr run without email to check all invoices:")
        check_invoice_status()
