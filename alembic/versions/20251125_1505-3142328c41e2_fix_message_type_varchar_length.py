"""fix_message_type_varchar_length

Revision ID: 3142328c41e2
Revises: 20251125_1600
Create Date: 2025-11-25 15:05:53.025267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3142328c41e2'
down_revision: Union[str, None] = '20251125_1600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter the type column to allow longer strings (up to 10 characters)
    # This is necessary because 'SYSTEM' is 6 characters, but the column was VARCHAR(5)
    op.execute("""
        ALTER TABLE messages
        ALTER COLUMN type TYPE VARCHAR(10);
    """)


def downgrade() -> None:
    # Revert to VARCHAR(5) - note this may fail if 'SYSTEM' messages exist
    op.execute("""
        ALTER TABLE messages
        ALTER COLUMN type TYPE VARCHAR(5);
    """)
