"""fix_message_created_at_default

Revision ID: 5d6021a9f1e5
Revises: b87d27a5bfd8
Create Date: 2025-10-17 16:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d6021a9f1e5'
down_revision: Union[str, None] = 'b87d27a5bfd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix the server_default for created_at to use CURRENT_TIMESTAMP
    # This ensures new messages get the current database time
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN created_at 
        SET DEFAULT CURRENT_TIMESTAMP;
    """)
    
    # Also update any existing messages that might have incorrect timestamps
    # (older than the table creation date which was 2025-10-10)
    op.execute("""
        UPDATE messages 
        SET created_at = CURRENT_TIMESTAMP 
        WHERE created_at < '2025-10-10'::timestamp;
    """)


def downgrade() -> None:
    # Revert to previous default
    op.execute("""
        ALTER TABLE messages 
        ALTER COLUMN created_at 
        SET DEFAULT now();
    """)
