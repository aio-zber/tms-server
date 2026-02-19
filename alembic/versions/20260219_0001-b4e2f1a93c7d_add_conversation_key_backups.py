"""Add conversation_key_backups table for multi-device E2EE session recovery

Revision ID: b4e2f1a93c7d
Revises: 9853d58ad1e4
Create Date: 2026-02-19 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4e2f1a93c7d'
down_revision: Union[str, None] = '9853d58ad1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_key_backups',
        sa.Column('id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('conversation_id', sa.String(255), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.Column('nonce', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'conversation_id', name='uq_user_conversation_key_backup'),
    )
    op.create_index('ix_conversation_key_backups_user_id', 'conversation_key_backups', ['user_id'])
    op.create_index('ix_conversation_key_backups_conversation_id', 'conversation_key_backups', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('ix_conversation_key_backups_conversation_id', table_name='conversation_key_backups')
    op.drop_index('ix_conversation_key_backups_user_id', table_name='conversation_key_backups')
    op.drop_table('conversation_key_backups')
