"""
Scope Proposal Background Worker
Processes email reminders and auto-expires overdue proposals
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import ScopeEmailReminder, ScopeProposal, ScopeProposalAuditLog
from ..services.scope_email_service import (
    send_24h_reminder_email,
    send_47h_reminder_email,
    send_expiry_notification_email,
)

logger = logging.getLogger(__name__)


async def process_pending_reminders():
    """
    Process all pending email reminders that are due
    """
    logger.info("🔄 Processing pending scope reminders...")

    db = SessionLocal()
    try:
        # Get all pending reminders that are due
        now = datetime.utcnow()
        pending_reminders = (
            db.query(ScopeEmailReminder)
            .filter(
                and_(
                    ScopeEmailReminder.status == "pending",
                    ScopeEmailReminder.scheduled_for <= now,
                )
            )
            .all()
        )

        if not pending_reminders:
            logger.info("✅ No pending reminders to process")
            return

        logger.info(f"📧 Processing {len(pending_reminders)} reminders")

        for reminder in pending_reminders:
            try:
                # Get proposal
                proposal = (
                    db.query(ScopeProposal).filter(ScopeProposal.id == reminder.proposal_id).first()
                )

                if not proposal:
                    logger.warning(
                        f"⚠️ Proposal {reminder.proposal_id} not found, cancelling reminder"
                    )
                    reminder.status = "cancelled"
                    db.commit()
                    continue

                # Skip if proposal is no longer in sent/viewed status
                if proposal.status not in ["sent", "viewed"]:
                    logger.info(
                        f"⏭️ Skipping reminder for proposal {proposal.id} (status: {proposal.status})"
                    )
                    reminder.status = "cancelled"
                    db.commit()
                    continue

                # Send appropriate reminder
                success = False
                if reminder.reminder_type == "24h_reminder":
                    success = await send_24h_reminder_email(proposal, db)
                elif reminder.reminder_type == "47h_reminder":
                    success = await send_47h_reminder_email(proposal, db)
                elif reminder.reminder_type == "expiry_notification":
                    success = await send_expiry_notification_email(proposal, db)

                # Update reminder status
                if success:
                    reminder.status = "sent"
                    reminder.sent_at = datetime.utcnow()
                    logger.info(f"✅ Sent {reminder.reminder_type} for proposal {proposal.id}")
                else:
                    reminder.status = "failed"
                    reminder.retry_count += 1
                    reminder.error_message = "Failed to send email"
                    logger.error(
                        f"❌ Failed to send {reminder.reminder_type} for proposal {proposal.id}"
                    )

                db.commit()

            except Exception as e:
                logger.error(f"❌ Error processing reminder {reminder.id}: {e}")
                reminder.status = "failed"
                reminder.retry_count += 1
                reminder.error_message = str(e)
                db.commit()

        logger.info("✅ Finished processing reminders")

    except Exception as e:
        logger.error(f"❌ Error in process_pending_reminders: {e}")
    finally:
        db.close()


async def expire_overdue_proposals():
    """
    Auto-expire proposals that have passed their deadline
    """
    logger.info("🔄 Checking for overdue proposals...")

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Find proposals that are overdue
        overdue_proposals = (
            db.query(ScopeProposal)
            .filter(
                and_(
                    ScopeProposal.status.in_(["sent", "viewed"]),
                    ScopeProposal.review_deadline <= now,
                )
            )
            .all()
        )

        if not overdue_proposals:
            logger.info("✅ No overdue proposals found")
            return

        logger.info(f"⏰ Found {len(overdue_proposals)} overdue proposals")

        for proposal in overdue_proposals:
            try:
                old_status = proposal.status

                # Mark as expired
                proposal.status = "expired"
                db.commit()

                # Create audit log
                audit_log = ScopeProposalAuditLog(
                    proposal_id=proposal.id,
                    action="expired",
                    actor_type="system",
                    old_status=old_status,
                    new_status="expired",
                    notes="Automatically expired due to deadline passing",
                )
                db.add(audit_log)
                db.commit()

                # Send expiry notification to provider (if not already sent)
                if not proposal.expiry_notification_sent:
                    await send_expiry_notification_email(proposal, db)

                logger.info(f"✅ Expired proposal {proposal.id}")

            except Exception as e:
                logger.error(f"❌ Error expiring proposal {proposal.id}: {e}")
                db.rollback()

        logger.info("✅ Finished expiring overdue proposals")

    except Exception as e:
        logger.error(f"❌ Error in expire_overdue_proposals: {e}")
    finally:
        db.close()


async def retry_failed_reminders():
    """
    Retry failed reminders (up to 3 attempts)
    """
    logger.info("🔄 Retrying failed reminders...")

    db = SessionLocal()
    try:
        # Get failed reminders with retry count < 3
        failed_reminders = (
            db.query(ScopeEmailReminder)
            .filter(
                and_(
                    ScopeEmailReminder.status == "failed",
                    ScopeEmailReminder.retry_count < 3,
                )
            )
            .all()
        )

        if not failed_reminders:
            logger.info("✅ No failed reminders to retry")
            return

        logger.info(f"🔁 Retrying {len(failed_reminders)} failed reminders")

        for reminder in failed_reminders:
            try:
                # Get proposal
                proposal = (
                    db.query(ScopeProposal).filter(ScopeProposal.id == reminder.proposal_id).first()
                )

                if not proposal or proposal.status not in ["sent", "viewed"]:
                    reminder.status = "cancelled"
                    db.commit()
                    continue

                # Retry sending
                success = False
                if reminder.reminder_type == "24h_reminder":
                    success = await send_24h_reminder_email(proposal, db)
                elif reminder.reminder_type == "47h_reminder":
                    success = await send_47h_reminder_email(proposal, db)
                elif reminder.reminder_type == "expiry_notification":
                    success = await send_expiry_notification_email(proposal, db)

                if success:
                    reminder.status = "sent"
                    reminder.sent_at = datetime.utcnow()
                    reminder.error_message = None
                    logger.info(f"✅ Retry successful for reminder {reminder.id}")
                else:
                    reminder.retry_count += 1
                    logger.warning(
                        f"⚠️ Retry failed for reminder {reminder.id} (attempt {reminder.retry_count})"
                    )

                db.commit()

            except Exception as e:
                logger.error(f"❌ Error retrying reminder {reminder.id}: {e}")
                reminder.retry_count += 1
                reminder.error_message = str(e)
                db.commit()

        logger.info("✅ Finished retrying failed reminders")

    except Exception as e:
        logger.error(f"❌ Error in retry_failed_reminders: {e}")
    finally:
        db.close()


async def run_scope_worker():
    """
    Main worker loop - runs every minute
    """
    logger.info("🚀 Starting scope proposal worker...")

    while True:
        try:
            # Process pending reminders
            await process_pending_reminders()

            # Expire overdue proposals
            await expire_overdue_proposals()

            # Retry failed reminders
            await retry_failed_reminders()

            # Wait 1 minute before next run
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"❌ Error in scope worker loop: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    # Run worker
    asyncio.run(run_scope_worker())
