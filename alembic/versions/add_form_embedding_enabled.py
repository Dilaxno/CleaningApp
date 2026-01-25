"""add form embedding enabled

Revision ID: add_form_embedding_enabled
Revises: increase_calendly_token_size
Create Date: 2026-01-24 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_form_embedding_enabled"
down_revision = "increase_calendly_token_size"
branch_labels = None
depends_on = None


def upgrade():
    # Add form_embedding_enabled column to business_configs table
    op.add_column(
        "business_configs",
        sa.Column("form_embedding_enabled", sa.Boolean(), nullable=True),
    )

    # Set default value for existing rows
    op.execute(
        "UPDATE business_configs SET form_embedding_enabled = FALSE WHERE form_embedding_enabled IS NULL"
    )

    # Make column non-nullable after setting defaults
    op.alter_column("business_configs", "form_embedding_enabled", nullable=False)


def downgrade():
    # Remove form_embedding_enabled column
    op.drop_column("business_configs", "form_embedding_enabled")
