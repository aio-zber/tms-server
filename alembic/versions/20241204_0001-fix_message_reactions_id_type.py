"""Fix message_reactions.id column type from UUID to VARCHAR

Revision ID: 20241204_0001
Revises: 20251202_0001
Create Date: 2024-12-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20241204_0001'
down_revision = 'cuid_support_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert message_reactions.id from UUID to VARCHAR(255)."""
    op.alter_column('message_reactions', 'id',
        existing_type=postgresql.UUID(),
        type_=sa.String(length=255),
        existing_nullable=False,
        postgresql_using='id::text')


def downgrade() -> None:
    """Revert message_reactions.id from VARCHAR(255) to UUID."""
    op.alter_column('message_reactions', 'id',
        existing_type=sa.String(length=255),
        type_=postgresql.UUID(),
        existing_nullable=False,
        postgresql_using='id::uuid')
