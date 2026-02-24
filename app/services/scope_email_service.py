"""
Scope of Work Email Notification Service
Sends review links, reminders, and expiry notifications
"""

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..email_service import send_email
from ..models import BusinessConfig, Client, ScopeProposal, User

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


async def send_scope_review_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Send initial scope review email to client
    """
    logger.info(f"📧 Sending scope review email for proposal {proposal.id}")

    try:
        # Get related data
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == proposal.user_id).first()
        )

        if not client.email:
            logger.error(f"❌ Client {client.id} has no email address")
            return False

        # Build review link
        review_link = f"{FRONTEND_URL}/scope-review/{proposal.review_token}"

        # Calculate deadline
        deadline_str = (
            proposal.review_deadline.strftime("%B %d, %Y at %I:%M %p")
            if proposal.review_deadline
            else "48 hours"
        )

        # Email subject
        subject = (
            f"Scope of Work Review Required - {business_config.business_name or user.full_name}"
        )

        # Email body
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #14b8a6; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">Scope of Work Review</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Hello {client.contact_name or client.business_name},</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    {business_config.business_name or user.full_name} has prepared a detailed Scope of Work 
                    for your cleaning services. Please review and respond by <strong>{deadline_str}</strong>.
                </p>
                
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #14b8a6;">
                    <p style="margin: 0; color: #64748b; font-size: 12px;">PROPERTY</p>
                    <p style="margin: 5px 0 0 0; color: #1e293b; font-size: 14px; font-weight: bold;">{client.business_name}</p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{review_link}" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        Review Scope of Work
                    </a>
                </div>
                
                <div style="background-color: #fef3c7; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p style="margin: 0; color: #92400e; font-size: 13px;">
                        ⏰ <strong>Action Required:</strong> Please review and respond within 48 hours. 
                        You can approve the scope or request revisions.
                    </p>
                </div>
                
                <p style="font-size: 13px; color: #64748b; margin-top: 30px;">
                    If you have any questions, please contact {business_config.business_name or user.full_name} 
                    at {user.email}.
                </p>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated message from CleanEnroll
                </p>
            </div>
        </div>
        """

        # Send email
        await send_email(
            to_email=client.email,
            subject=subject,
            html_content=body,
            from_name=business_config.business_name or user.full_name,
        )

        # Mark as sent
        proposal.email_sent = True
        db.commit()

        logger.info(f"✅ Sent scope review email to {client.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send scope review email: {e}")
        return False


async def send_24h_reminder_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Send 24-hour reminder email
    """
    logger.info(f"📧 Sending 24h reminder for proposal {proposal.id}")

    try:
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == proposal.user_id).first()
        )

        if not client.email:
            return False

        review_link = f"{FRONTEND_URL}/scope-review/{proposal.review_token}"
        deadline_str = proposal.review_deadline.strftime("%B %d, %Y at %I:%M %p")

        subject = f"Reminder: Scope of Work Review Due in 24 Hours"

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f59e0b; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">⏰ Reminder: Review Due Soon</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Hello {client.contact_name or client.business_name},</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    This is a friendly reminder that your Scope of Work review is due in 
                    <strong>24 hours</strong> (by {deadline_str}).
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{review_link}" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        Review Now
                    </a>
                </div>
                
                <p style="font-size: 13px; color: #64748b;">
                    If you've already reviewed this, please disregard this reminder.
                </p>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated reminder from CleanEnroll
                </p>
            </div>
        </div>
        """

        await send_email(
            to_email=client.email,
            subject=subject,
            html_content=body,
            from_name=business_config.business_name or user.full_name,
        )

        proposal.reminder_24h_sent = True
        db.commit()

        logger.info(f"✅ Sent 24h reminder to {client.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send 24h reminder: {e}")
        return False


async def send_47h_reminder_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Send 47-hour (1 hour before deadline) reminder email
    """
    logger.info(f"📧 Sending 47h reminder for proposal {proposal.id}")

    try:
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()
        business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == proposal.user_id).first()
        )

        if not client.email:
            return False

        review_link = f"{FRONTEND_URL}/scope-review/{proposal.review_token}"
        deadline_str = proposal.review_deadline.strftime("%I:%M %p")

        subject = f"URGENT: Scope of Work Review Due in 1 Hour"

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #dc2626; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">🚨 Final Reminder: Review Due in 1 Hour</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Hello {client.contact_name or client.business_name},</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    Your Scope of Work review deadline is approaching. You have 
                    <strong>1 hour remaining</strong> (until {deadline_str} today).
                </p>
                
                <div style="background-color: #fee2e2; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc2626;">
                    <p style="margin: 0; color: #991b1b; font-size: 13px;">
                        ⚠️ <strong>Action Required:</strong> If you don't respond by the deadline, 
                        this review link will expire and you'll need to request a new one.
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{review_link}" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        Review Immediately
                    </a>
                </div>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated reminder from CleanEnroll
                </p>
            </div>
        </div>
        """

        await send_email(
            to_email=client.email,
            subject=subject,
            html_content=body,
            from_name=business_config.business_name or user.full_name,
        )

        proposal.reminder_47h_sent = True
        db.commit()

        logger.info(f"✅ Sent 47h reminder to {client.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send 47h reminder: {e}")
        return False


async def send_expiry_notification_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Send expiry notification to provider
    """
    logger.info(f"📧 Sending expiry notification for proposal {proposal.id}")

    try:
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()

        subject = f"Scope of Work Review Expired - {client.business_name}"

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #64748b; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">Scope Review Expired</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Hello {user.full_name},</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    The Scope of Work review for <strong>{client.business_name}</strong> has expired 
                    without a response from the client.
                </p>
                
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; color: #64748b; font-size: 12px;">PROPOSAL DETAILS</p>
                    <p style="margin: 5px 0; color: #1e293b;"><strong>Client:</strong> {client.business_name}</p>
                    <p style="margin: 5px 0; color: #1e293b;"><strong>Version:</strong> {proposal.version}</p>
                    <p style="margin: 5px 0; color: #1e293b;"><strong>Status:</strong> Expired</p>
                </div>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    You can resend the scope for review from your dashboard, which will generate 
                    a new review link with a fresh 48-hour deadline.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{FRONTEND_URL}/dashboard" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        Go to Dashboard
                    </a>
                </div>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated notification from CleanEnroll
                </p>
            </div>
        </div>
        """

        await send_email(
            to_email=user.email, subject=subject, html_content=body, from_name="CleanEnroll"
        )

        proposal.expiry_notification_sent = True
        db.commit()

        logger.info(f"✅ Sent expiry notification to {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send expiry notification: {e}")
        return False


async def send_approval_notification_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Notify provider when client approves scope
    """
    logger.info(f"📧 Sending approval notification for proposal {proposal.id}")

    try:
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()

        subject = f"✅ Scope of Work Approved - {client.business_name}"

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #10b981; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">✅ Scope Approved!</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Great news, {user.full_name}!</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    <strong>{client.business_name}</strong> has approved the Scope of Work ({proposal.version}).
                </p>
                
                <div style="background-color: #d1fae5; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #10b981;">
                    <p style="margin: 0; color: #065f46; font-size: 13px;">
                        ✓ The approved scope is now attached to the contract and ready for service delivery.
                    </p>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{FRONTEND_URL}/dashboard" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        View Dashboard
                    </a>
                </div>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated notification from CleanEnroll
                </p>
            </div>
        </div>
        """

        await send_email(
            to_email=user.email, subject=subject, html_content=body, from_name="CleanEnroll"
        )

        logger.info(f"✅ Sent approval notification to {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send approval notification: {e}")
        return False


async def send_revision_request_notification_email(proposal: ScopeProposal, db: Session) -> bool:
    """
    Notify provider when client requests revisions
    """
    logger.info(f"📧 Sending revision request notification for proposal {proposal.id}")

    try:
        user = db.query(User).filter(User.id == proposal.user_id).first()
        client = db.query(Client).filter(Client.id == proposal.client_id).first()

        subject = f"Revision Requested - {client.business_name}"

        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f59e0b; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">📝 Revision Requested</h1>
            </div>
            
            <div style="padding: 30px; background-color: #f9fafb;">
                <p style="font-size: 16px; color: #1e293b;">Hello {user.full_name},</p>
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    <strong>{client.business_name}</strong> has requested revisions to the Scope of Work ({proposal.version}).
                </p>
                
                {f'''
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                    <p style="margin: 0 0 10px 0; color: #92400e; font-size: 12px; font-weight: bold;">CLIENT NOTES:</p>
                    <p style="margin: 0; color: #1e293b; font-size: 14px;">{proposal.client_revision_notes}</p>
                </div>
                ''' if proposal.client_revision_notes else ''}
                
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    Please review the feedback and create an updated scope proposal.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{FRONTEND_URL}/dashboard" 
                       style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                              text-decoration: none; border-radius: 6px; font-weight: bold; 
                              display: inline-block; font-size: 16px;">
                        Create Revised Scope
                    </a>
                </div>
            </div>
            
            <div style="background-color: #1e293b; padding: 20px; text-align: center;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                    This is an automated notification from CleanEnroll
                </p>
            </div>
        </div>
        """

        await send_email(
            to_email=user.email, subject=subject, html_content=body, from_name="CleanEnroll"
        )

        logger.info(f"✅ Sent revision request notification to {user.email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send revision request notification: {e}")
        return False
