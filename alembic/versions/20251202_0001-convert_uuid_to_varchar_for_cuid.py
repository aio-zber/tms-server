"""Convert UUID columns to VARCHAR for CUID support

Revision ID: cuid_support_001
Revises: clean_notif_001
Create Date: 2025-12-02 00:01:00.000000

This migration converts all UUID columns to VARCHAR(255) to support CUID format IDs
from TMS instead of standard UUID format.

CUID format: 25 characters (e.g., 'cmgoip1nt0001s89pzkw7bzlg')
UUID format: 36 characters (e.g., '550e8400-e29b-41d4-a716-446655440000')
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cuid_support_001'
down_revision: Union[str, None] = 'clean_notif_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Convert all UUID columns to VARCHAR(255) to support CUID strings from TMS.

    Order of operations:
    1. Drop foreign key constraints
    2. Convert primary key columns
    3. Convert foreign key columns
    4. Recreate foreign key constraints
    """

    # Step 1: Drop all foreign key constraints (we'll recreate them later)
    op.drop_constraint('muted_conversations_user_id_fkey', 'muted_conversations', type_='foreignkey')
    op.drop_constraint('muted_conversations_conversation_id_fkey', 'muted_conversations', type_='foreignkey')
    op.drop_constraint('notification_preferences_user_id_fkey', 'notification_preferences', type_='foreignkey')
    op.drop_constraint('conversation_members_user_id_fkey', 'conversation_members', type_='foreignkey')
    op.drop_constraint('conversation_members_conversation_id_fkey', 'conversation_members', type_='foreignkey')
    op.drop_constraint('conversations_created_by_fkey', 'conversations', type_='foreignkey')
    op.drop_constraint('messages_sender_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('messages_conversation_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('messages_reply_to_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('message_status_user_id_fkey', 'message_status', type_='foreignkey')
    op.drop_constraint('message_status_message_id_fkey', 'message_status', type_='foreignkey')
    op.drop_constraint('message_reactions_user_id_fkey', 'message_reactions', type_='foreignkey')
    op.drop_constraint('message_reactions_message_id_fkey', 'message_reactions', type_='foreignkey')
    op.drop_constraint('user_blocks_blocker_id_fkey', 'user_blocks', type_='foreignkey')
    op.drop_constraint('user_blocks_blocked_id_fkey', 'user_blocks', type_='foreignkey')
    op.drop_constraint('calls_conversation_id_fkey', 'calls', type_='foreignkey')
    op.drop_constraint('calls_created_by_fkey', 'calls', type_='foreignkey')
    op.drop_constraint('call_participants_call_id_fkey', 'call_participants', type_='foreignkey')
    op.drop_constraint('call_participants_user_id_fkey', 'call_participants', type_='foreignkey')
    # Poll-related foreign keys
    op.drop_constraint('polls_message_id_fkey', 'polls', type_='foreignkey')
    op.drop_constraint('poll_options_poll_id_fkey', 'poll_options', type_='foreignkey')
    op.drop_constraint('poll_votes_poll_id_fkey', 'poll_votes', type_='foreignkey')
    op.drop_constraint('poll_votes_option_id_fkey', 'poll_votes', type_='foreignkey')
    op.drop_constraint('poll_votes_user_id_fkey', 'poll_votes', type_='foreignkey')

    # Step 2: Convert primary key columns in base tables
    # Users table
    op.alter_column('users', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Conversations table
    op.alter_column('conversations', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Messages table
    op.alter_column('messages', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Calls table
    op.alter_column('calls', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Notification preferences table
    op.alter_column('notification_preferences', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Muted conversations table
    op.alter_column('muted_conversations', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')

    # Step 3: Convert foreign key columns
    # Conversations
    op.alter_column('conversations', 'created_by',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=True,
                    postgresql_using='created_by::text')

    # Conversation members
    op.alter_column('conversation_members', 'conversation_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='conversation_id::text')
    op.alter_column('conversation_members', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # Messages
    op.alter_column('messages', 'conversation_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='conversation_id::text')
    op.alter_column('messages', 'sender_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='sender_id::text')
    op.alter_column('messages', 'reply_to_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=True,
                    postgresql_using='reply_to_id::text')

    # Message status
    op.alter_column('message_status', 'message_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='message_id::text')
    op.alter_column('message_status', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # Message reactions
    op.alter_column('message_reactions', 'message_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='message_id::text')
    op.alter_column('message_reactions', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # User blocks
    op.alter_column('user_blocks', 'blocker_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='blocker_id::text')
    op.alter_column('user_blocks', 'blocked_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='blocked_id::text')

    # Calls
    op.alter_column('calls', 'conversation_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='conversation_id::text')
    op.alter_column('calls', 'created_by',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='created_by::text')

    # Call participants
    op.alter_column('call_participants', 'call_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='call_id::text')
    op.alter_column('call_participants', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # Notification preferences
    op.alter_column('notification_preferences', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # Muted conversations
    op.alter_column('muted_conversations', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')
    op.alter_column('muted_conversations', 'conversation_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='conversation_id::text')

    # Polls
    op.alter_column('polls', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')
    op.alter_column('polls', 'message_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='message_id::text')

    # Poll options
    op.alter_column('poll_options', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')
    op.alter_column('poll_options', 'poll_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='poll_id::text')

    # Poll votes
    op.alter_column('poll_votes', 'id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='id::text')
    op.alter_column('poll_votes', 'poll_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='poll_id::text')
    op.alter_column('poll_votes', 'option_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='option_id::text')
    op.alter_column('poll_votes', 'user_id',
                    existing_type=postgresql.UUID(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    postgresql_using='user_id::text')

    # Step 4: Recreate foreign key constraints
    op.create_foreign_key('muted_conversations_user_id_fkey', 'muted_conversations', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('muted_conversations_conversation_id_fkey', 'muted_conversations', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('notification_preferences_user_id_fkey', 'notification_preferences', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversation_members_user_id_fkey', 'conversation_members', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversation_members_conversation_id_fkey', 'conversation_members', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversations_created_by_fkey', 'conversations', 'users', ['created_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('messages_sender_id_fkey', 'messages', 'users', ['sender_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('messages_conversation_id_fkey', 'messages', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('messages_reply_to_id_fkey', 'messages', 'messages', ['reply_to_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('message_status_user_id_fkey', 'message_status', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_status_message_id_fkey', 'message_status', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_reactions_user_id_fkey', 'message_reactions', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_reactions_message_id_fkey', 'message_reactions', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('user_blocks_blocker_id_fkey', 'user_blocks', 'users', ['blocker_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('user_blocks_blocked_id_fkey', 'user_blocks', 'users', ['blocked_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('calls_conversation_id_fkey', 'calls', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('calls_created_by_fkey', 'calls', 'users', ['created_by'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('call_participants_call_id_fkey', 'call_participants', 'calls', ['call_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('call_participants_user_id_fkey', 'call_participants', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    # Poll foreign keys
    op.create_foreign_key('polls_message_id_fkey', 'polls', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('poll_options_poll_id_fkey', 'poll_options', 'polls', ['poll_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('poll_votes_poll_id_fkey', 'poll_votes', 'polls', ['poll_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('poll_votes_option_id_fkey', 'poll_votes', 'poll_options', ['option_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('poll_votes_user_id_fkey', 'poll_votes', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """
    Revert VARCHAR columns back to UUID.
    WARNING: This may fail if CUIDs are present in the data.
    """

    # Drop foreign key constraints
    op.drop_constraint('muted_conversations_user_id_fkey', 'muted_conversations', type_='foreignkey')
    op.drop_constraint('muted_conversations_conversation_id_fkey', 'muted_conversations', type_='foreignkey')
    op.drop_constraint('notification_preferences_user_id_fkey', 'notification_preferences', type_='foreignkey')
    op.drop_constraint('conversation_members_user_id_fkey', 'conversation_members', type_='foreignkey')
    op.drop_constraint('conversation_members_conversation_id_fkey', 'conversation_members', type_='foreignkey')
    op.drop_constraint('conversations_created_by_fkey', 'conversations', type_='foreignkey')
    op.drop_constraint('messages_sender_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('messages_conversation_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('messages_reply_to_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('message_status_user_id_fkey', 'message_status', type_='foreignkey')
    op.drop_constraint('message_status_message_id_fkey', 'message_status', type_='foreignkey')
    op.drop_constraint('message_reactions_user_id_fkey', 'message_reactions', type_='foreignkey')
    op.drop_constraint('message_reactions_message_id_fkey', 'message_reactions', type_='foreignkey')
    op.drop_constraint('user_blocks_blocker_id_fkey', 'user_blocks', type_='foreignkey')
    op.drop_constraint('user_blocks_blocked_id_fkey', 'user_blocks', type_='foreignkey')
    op.drop_constraint('calls_conversation_id_fkey', 'calls', type_='foreignkey')
    op.drop_constraint('calls_created_by_fkey', 'calls', type_='foreignkey')
    op.drop_constraint('call_participants_call_id_fkey', 'call_participants', type_='foreignkey')
    op.drop_constraint('call_participants_user_id_fkey', 'call_participants', type_='foreignkey')
    # Poll foreign keys
    op.drop_constraint('polls_message_id_fkey', 'polls', type_='foreignkey')
    op.drop_constraint('poll_options_poll_id_fkey', 'poll_options', type_='foreignkey')
    op.drop_constraint('poll_votes_poll_id_fkey', 'poll_votes', type_='foreignkey')
    op.drop_constraint('poll_votes_option_id_fkey', 'poll_votes', type_='foreignkey')
    op.drop_constraint('poll_votes_user_id_fkey', 'poll_votes', type_='foreignkey')

    # Convert back to UUID (reverse order)
    op.alter_column('muted_conversations', 'conversation_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='conversation_id::uuid')
    op.alter_column('muted_conversations', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('muted_conversations', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    op.alter_column('notification_preferences', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('notification_preferences', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    op.alter_column('call_participants', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('call_participants', 'call_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='call_id::uuid')

    op.alter_column('calls', 'created_by',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='created_by::uuid')
    op.alter_column('calls', 'conversation_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='conversation_id::uuid')
    op.alter_column('calls', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    op.alter_column('user_blocks', 'blocked_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='blocked_id::uuid')
    op.alter_column('user_blocks', 'blocker_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='blocker_id::uuid')

    op.alter_column('message_reactions', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('message_reactions', 'message_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='message_id::uuid')

    op.alter_column('message_status', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('message_status', 'message_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='message_id::uuid')

    op.alter_column('messages', 'reply_to_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=True,
                    postgresql_using='reply_to_id::uuid')
    op.alter_column('messages', 'sender_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='sender_id::uuid')
    op.alter_column('messages', 'conversation_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='conversation_id::uuid')
    op.alter_column('messages', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    op.alter_column('conversation_members', 'user_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='user_id::uuid')
    op.alter_column('conversation_members', 'conversation_id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='conversation_id::uuid')

    op.alter_column('conversations', 'created_by',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=True,
                    postgresql_using='created_by::uuid')
    op.alter_column('conversations', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    op.alter_column('users', 'id',
                    existing_type=sa.String(length=255),
                    type_=postgresql.UUID(),
                    existing_nullable=False,
                    postgresql_using='id::uuid')

    # Recreate foreign key constraints with UUID
    op.create_foreign_key('muted_conversations_user_id_fkey', 'muted_conversations', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('muted_conversations_conversation_id_fkey', 'muted_conversations', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('notification_preferences_user_id_fkey', 'notification_preferences', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversation_members_user_id_fkey', 'conversation_members', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversation_members_conversation_id_fkey', 'conversation_members', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('conversations_created_by_fkey', 'conversations', 'users', ['created_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('messages_sender_id_fkey', 'messages', 'users', ['sender_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('messages_conversation_id_fkey', 'messages', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('messages_reply_to_id_fkey', 'messages', 'messages', ['reply_to_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('message_status_user_id_fkey', 'message_status', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_status_message_id_fkey', 'message_status', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_reactions_user_id_fkey', 'message_reactions', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('message_reactions_message_id_fkey', 'message_reactions', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('user_blocks_blocker_id_fkey', 'user_blocks', 'users', ['blocker_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('user_blocks_blocked_id_fkey', 'user_blocks', 'users', ['blocked_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('calls_conversation_id_fkey', 'calls', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('calls_created_by_fkey', 'calls', 'users', ['created_by'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('call_participants_call_id_fkey', 'call_participants', 'calls', ['call_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('call_participants_user_id_fkey', 'call_participants', 'users', ['user_id'], ['id'], ondelete='CASCADE')
