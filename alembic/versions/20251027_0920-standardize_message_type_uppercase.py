"""standardize message type enum to uppercase

Revision ID: a1b2c3d4e5f6
Revises: enable_pg_trgm_extension
Create Date: 2025-10-27 09:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Standardize message type enum values to uppercase.

    PostgreSQL was storing the enum NAME (e.g., 'POLL') instead of the VALUE (e.g., 'poll').
    This migration ensures all existing messages use uppercase type values to match
    the database reality and fix poll display issues.
    """
    # Update existing messages to use uppercase type values
    # These should already be uppercase in the DB, but we run this to be safe
    op.execute("""
        UPDATE messages
        SET type = UPPER(type)
        WHERE type IN ('text', 'image', 'file', 'voice', 'poll', 'call');
    """)

    # Note: PostgreSQL enum types are case-sensitive
    # The MessageType Python enum now uses uppercase values to match


def downgrade() -> None:
    """
    Revert message type enum values to lowercase.

    Note: This assumes we want to go back to lowercase values.
    """
    op.execute("""
        UPDATE messages
        SET type = LOWER(type)
        WHERE type IN ('TEXT', 'IMAGE', 'FILE', 'VOICE', 'POLL', 'CALL');
    """)
