"""add_user_deleted_messages_table

Revision ID: 1a009d41900d
Revises: 7ab8a008d2fe
Create Date: 2026-01-20 15:15:13.915108

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1a009d41900d'
down_revision: Union[str, None] = '7ab8a008d2fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add user_deleted_messages table for Messenger-style per-user message deletion.

    This table tracks which messages have been deleted "for me" by individual users,
    enabling:
    - "Delete for Me": Hides message only for the requesting user
    - "Clear Conversation": Clears chat history only for the requesting user
    """
    op.create_table('user_deleted_messages',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'message_id')
    )
    op.create_index('idx_user_deleted_messages_message', 'user_deleted_messages', ['message_id'], unique=False)
    op.create_index('idx_user_deleted_messages_user', 'user_deleted_messages', ['user_id'], unique=False)


def downgrade() -> None:
    """Remove user_deleted_messages table."""
    op.drop_index('idx_user_deleted_messages_user', table_name='user_deleted_messages')
    op.drop_index('idx_user_deleted_messages_message', table_name='user_deleted_messages')
    op.drop_table('user_deleted_messages')
