"""add system message type

Revision ID: 20251125_1600
Revises: 20251027_0920
Create Date: 2025-11-25 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251125_1600'
down_revision = '20251027_0920'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add SYSTEM to the message_type enum
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'SYSTEM'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values
    # This would require recreating the enum type and migrating data
    # For safety, we leave SYSTEM in the enum
    pass
