"""increase calendly token size

Revision ID: increase_calendly_token_size
Revises: 
Create Date: 2026-01-06 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'increase_calendly_token_size'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Change access_token and refresh_token from VARCHAR(500) to TEXT
    op.alter_column('calendly_integrations', 'access_token',
                    existing_type=sa.VARCHAR(length=500),
                    type_=sa.Text(),
                    existing_nullable=False)
    
    op.alter_column('calendly_integrations', 'refresh_token',
                    existing_type=sa.VARCHAR(length=500),
                    type_=sa.Text(),
                    existing_nullable=False)


def downgrade():
    # Revert TEXT back to VARCHAR(500)
    op.alter_column('calendly_integrations', 'access_token',
                    existing_type=sa.Text(),
                    type_=sa.VARCHAR(length=500),
                    existing_nullable=False)
    
    op.alter_column('calendly_integrations', 'refresh_token',
                    existing_type=sa.Text(),
                    type_=sa.VARCHAR(length=500),
                    existing_nullable=False)
