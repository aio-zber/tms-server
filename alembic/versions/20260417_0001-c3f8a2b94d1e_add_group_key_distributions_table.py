"""add_group_key_distributions_table

Per-recipient encrypted group key distribution (WhatsApp/Signal pattern).
The server stores one opaque encrypted blob per recipient — it never sees
the plaintext group key, only the intended recipient can decrypt their copy.

Revision ID: c3f8a2b94d1e
Revises: 773a0b61b305
Create Date: 2026-04-17 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a2b94d1e'
down_revision: Union[str, None] = '773a0b61b305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'group_key_distributions',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column(
            'conversation_id',
            sa.String(255),
            sa.ForeignKey('conversations.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'recipient_id',
            sa.String(255),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'sender_id',
            sa.String(255),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('sender_key_id', sa.String(64), nullable=False),
        sa.Column('encrypted_key', sa.Text, nullable=False),
        sa.Column('nonce', sa.Text, nullable=False),
        sa.Column('ephemeral_public_key', sa.Text, nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            'conversation_id', 'recipient_id',
            name='uq_group_key_distribution',
        ),
    )


def downgrade() -> None:
    op.drop_table('group_key_distributions')
