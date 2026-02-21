"""add_avatar_oss_key_to_conversations

Revision ID: 773a0b61b305
Revises: 75f5886aa87e
Create Date: 2026-02-20 15:59:21.073811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '773a0b61b305'
down_revision: Union[str, None] = '75f5886aa87e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('avatar_oss_key', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('conversations', 'avatar_oss_key')
