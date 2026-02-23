"""add_chain_key_to_group_sender_keys

Revision ID: 75f5886aa87e
Revises: b4e2f1a93c7d
Create Date: 2026-02-20 10:08:18.567452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '75f5886aa87e'
down_revision: Union[str, None] = 'b4e2f1a93c7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('group_sender_keys', sa.Column('chain_key', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('group_sender_keys', 'chain_key')
