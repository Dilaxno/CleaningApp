"""add zoho booking integration

Revision ID: add_zoho_booking_integration
Revises: increase_calendly_token_size
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = 'add_zoho_booking_integration'
down_revision = 'increase_calendly_token_size'
branch_labels = None
depends_on = None


def upgrade():
    # Create zoho_booking_integrations table
    op.create_table('zoho_booking_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(), nullable=False),
        sa.Column('zoho_user_id', sa.String(length=255), nullable=False),
        sa.Column('zoho_user_email', sa.String(length=255), nullable=True),
        sa.Column('zoho_org_id', sa.String(length=255), nullable=True),
        sa.Column('workspace_id', sa.String(length=255), nullable=True),
        sa.Column('workspace_name', sa.String(length=255), nullable=True),
        sa.Column('default_service_id', sa.String(length=255), nullable=True),
        sa.Column('default_service_name', sa.String(length=255), nullable=True),
        sa.Column('auto_sync_enabled', sa.Boolean(), nullable=True),
        sa.Column('webhook_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_zoho_booking_integrations_id'), 'zoho_booking_integrations', ['id'], unique=False)


def downgrade():
    # Drop zoho_booking_integrations table
    op.drop_index(op.f('ix_zoho_booking_integrations_id'), table_name='zoho_booking_integrations')
    op.drop_table('zoho_booking_integrations')