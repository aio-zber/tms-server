"""add_e2ee_tables_and_message_encryption_fields

Revision ID: 181f253987d5
Revises: 1a009d41900d
Create Date: 2026-02-04 15:19:48.893741

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '181f253987d5'
down_revision: Union[str, None] = '1a009d41900d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create E2EE key bundle tables
    op.create_table('user_key_bundles',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('identity_key', sa.Text(), nullable=False),
        sa.Column('signed_prekey', sa.Text(), nullable=False),
        sa.Column('signed_prekey_signature', sa.Text(), nullable=False),
        sa.Column('signed_prekey_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    op.create_table('one_time_prekeys',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('prekey_id', sa.Integer(), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'prekey_id', name='uq_user_prekey_id')
    )
    op.create_index(op.f('ix_one_time_prekeys_user_id'), 'one_time_prekeys', ['user_id'], unique=False)

    op.create_table('group_sender_keys',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('conversation_id', sa.String(length=255), nullable=False),
        sa.Column('sender_id', sa.String(length=255), nullable=False),
        sa.Column('sender_key_id', sa.String(length=64), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'sender_id', name='uq_conversation_sender')
    )
    op.create_index(op.f('ix_group_sender_keys_conversation_id'), 'group_sender_keys', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_group_sender_keys_sender_id'), 'group_sender_keys', ['sender_id'], unique=False)

    # Add E2EE fields to messages table
    # Use server_default for encrypted to handle existing rows
    op.add_column('messages', sa.Column('encrypted', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('messages', sa.Column('encryption_version', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('sender_key_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'sender_key_id')
    op.drop_column('messages', 'encryption_version')
    op.drop_column('messages', 'encrypted')
    op.drop_index(op.f('ix_group_sender_keys_sender_id'), table_name='group_sender_keys')
    op.drop_index(op.f('ix_group_sender_keys_conversation_id'), table_name='group_sender_keys')
    op.drop_table('group_sender_keys')
    op.drop_index(op.f('ix_one_time_prekeys_user_id'), table_name='one_time_prekeys')
    op.drop_table('one_time_prekeys')
    op.drop_table('user_key_bundles')
