"""add message sequence number for deterministic ordering

Revision ID: e7828e95503f
Revises: timestamptz_001
Create Date: 2026-01-05 09:49:21.225850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7828e95503f'
down_revision: Union[str, None] = 'timestamptz_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add sequence_number column to messages table for deterministic ordering.

    This migration:
    1. Adds sequence_number column (nullable initially for backfill)
    2. Backfills sequence numbers based on created_at order
    3. Makes sequence_number NOT NULL
    4. Creates composite index on (conversation_id, sequence_number DESC, created_at DESC)
    5. Adds unique constraint on (conversation_id, sequence_number)
    6. Drops old timestamp-only index
    """
    # Step 1: Add sequence_number column (nullable initially for backfill)
    op.add_column('messages',
        sa.Column('sequence_number', sa.BigInteger(), nullable=True)
    )

    # Step 2: Backfill sequence numbers based on created_at order
    # This assigns sequences to maintain current message order
    op.execute("""
        WITH ranked_messages AS (
            SELECT
                id,
                conversation_id,
                ROW_NUMBER() OVER (
                    PARTITION BY conversation_id
                    ORDER BY created_at ASC, id ASC
                ) as seq
            FROM messages
        )
        UPDATE messages m
        SET sequence_number = r.seq
        FROM ranked_messages r
        WHERE m.id = r.id
    """)

    # Step 3: Make sequence_number NOT NULL now that all rows have values
    op.alter_column('messages', 'sequence_number', nullable=False)

    # Step 4: Create composite index for efficient ordering
    # This replaces idx_messages_conversation_created
    op.create_index(
        'idx_messages_conversation_seq',
        'messages',
        ['conversation_id', sa.text('sequence_number DESC'), sa.text('created_at DESC')],
        unique=False
    )

    # Step 5: Add unique constraint to prevent duplicate sequences
    op.create_unique_constraint(
        'uq_conversation_sequence',
        'messages',
        ['conversation_id', 'sequence_number']
    )

    # Step 6: Drop old index (superseded by new composite index)
    op.drop_index(
        'idx_messages_conversation_created',
        table_name='messages'
    )


def downgrade() -> None:
    """
    Rollback: Remove sequence_number column and restore old index.
    """
    # Recreate old index
    op.create_index(
        'idx_messages_conversation_created',
        'messages',
        ['conversation_id', sa.text('created_at DESC')],
        unique=False
    )

    # Drop unique constraint
    op.drop_constraint('uq_conversation_sequence', 'messages', type_='unique')

    # Drop new index
    op.drop_index('idx_messages_conversation_seq', table_name='messages')

    # Drop sequence_number column
    op.drop_column('messages', 'sequence_number')
