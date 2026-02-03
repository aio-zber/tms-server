"""fix_timestamps_and_add_performance_indexes

Revision ID: b87d27a5bfd8
Revises: b2ec88244e3f
Create Date: 2025-10-17 14:20:03.116094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b87d27a5bfd8'
down_revision: Union[str, None] = 'b2ec88244e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Fix message timestamps to use server default (current timestamp)
    2. Add critical performance indexes
    """
    
    # Fix timestamps: Ensure created_at has proper server default
    op.alter_column('messages', 'created_at',
                    existing_type=sa.DateTime(),
                    server_default=sa.text('now()'),
                    nullable=False)
    
    # Add composite index for optimized message pagination
    # This is CRITICAL for fast queries with ORDER BY created_at, id
    op.create_index(
        'idx_messages_conversation_created_id',
        'messages',
        ['conversation_id', 'created_at', 'id'],
        unique=False
    )
    
    # Add index for sender queries
    op.create_index(
        'idx_messages_sender',
        'messages',
        ['sender_id'],
        unique=False
    )
    
    # Add index for reply lookups
    op.create_index(
        'idx_messages_reply_to',
        'messages',
        ['reply_to_id'],
        unique=False
    )
    
    # Add index for message reactions
    op.create_index(
        'idx_message_reactions_message',
        'message_reactions',
        ['message_id'],
        unique=False
    )
    
    # Add index for user's reactions
    op.create_index(
        'idx_message_reactions_user',
        'message_reactions',
        ['user_id'],
        unique=False
    )
    
    # Add index for message status queries
    op.create_index(
        'idx_message_status_message_user',
        'message_status',
        ['message_id', 'user_id'],
        unique=False
    )
    
    # Add index for conversation members
    op.create_index(
        'idx_conversation_members_user',
        'conversation_members',
        ['user_id'],
        unique=False
    )
    
    # Add index for TMS user ID lookups (critical for auth)
    op.create_index(
        'idx_users_tms_user_id',
        'users',
        ['tms_user_id'],
        unique=True
    )


def downgrade() -> None:
    """Remove indexes and revert timestamp changes."""
    
    # Drop indexes
    op.drop_index('idx_users_tms_user_id', table_name='users')
    op.drop_index('idx_conversation_members_user', table_name='conversation_members')
    op.drop_index('idx_message_status_message_user', table_name='message_status')
    op.drop_index('idx_message_reactions_user', table_name='message_reactions')
    op.drop_index('idx_message_reactions_message', table_name='message_reactions')
    op.drop_index('idx_messages_reply_to', table_name='messages')
    op.drop_index('idx_messages_sender', table_name='messages')
    op.drop_index('idx_messages_conversation_created_id', table_name='messages')
    
    # Revert timestamp change (remove server default)
    op.alter_column('messages', 'created_at',
                    existing_type=sa.DateTime(),
                    server_default=None,
                    nullable=False)
