"""Add notification preferences and muted conversations (clean)

Revision ID: clean_notif_001
Revises: 3142328c41e2
Create Date: 2025-12-01 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'clean_notif_001'
down_revision: Union[str, None] = '3142328c41e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notification_preferences and muted_conversations tables only."""

    # Create notification_preferences table
    op.create_table(
        'notification_preferences',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('sound_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sound_volume', sa.Integer(), server_default='75', nullable=False),
        sa.Column('browser_notifications_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('enable_message_notifications', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('enable_mention_notifications', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('enable_reaction_notifications', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('enable_member_activity_notifications', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('dnd_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('dnd_start', sa.Time(), nullable=True),
        sa.Column('dnd_end', sa.Time(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_notification_preferences_user_id'),
        'notification_preferences',
        ['user_id'],
        unique=True
    )

    # Create muted_conversations table
    op.create_table(
        'muted_conversations',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('muted_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'conversation_id', name='uq_muted_conversations_user_conversation')
    )
    op.create_index(
        'ix_muted_conversations_conversation_id',
        'muted_conversations',
        ['conversation_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_muted_conversations_user_id'),
        'muted_conversations',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove notification tables."""
    op.drop_index(op.f('ix_muted_conversations_user_id'), table_name='muted_conversations')
    op.drop_index('ix_muted_conversations_conversation_id', table_name='muted_conversations')
    op.drop_table('muted_conversations')
    op.drop_index(op.f('ix_notification_preferences_user_id'), table_name='notification_preferences')
    op.drop_table('notification_preferences')
