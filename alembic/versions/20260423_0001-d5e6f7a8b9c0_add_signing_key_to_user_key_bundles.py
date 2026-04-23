"""add_signing_key_to_user_key_bundles

Adds Ed25519 public signing key to user_key_bundles table.
Required for SPK signature verification in X3DH (Fix 5).

Revision ID: d5e6f7a8b9c0
Revises: c3f8a2b94d1e
Create Date: 2026-04-23 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c3f8a2b94d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_key_bundles',
        sa.Column('signing_key', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('user_key_bundles', 'signing_key')
