"""Add three-category time estimation system

Revision ID: add_three_category_time_estimation
Revises: 
Create Date: 2026-01-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_three_category_time_estimation'
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Add new three-category time estimation fields
    op.add_column('business_configs', sa.Column('time_small_job', sa.Float(), nullable=True))
    op.add_column('business_configs', sa.Column('time_medium_job', sa.Float(), nullable=True))
    op.add_column('business_configs', sa.Column('time_large_job', sa.Float(), nullable=True))


def downgrade():
    # Remove the new fields
    op.drop_column('business_configs', 'time_large_job')
    op.drop_column('business_configs', 'time_medium_job')
    op.drop_column('business_configs', 'time_small_job')