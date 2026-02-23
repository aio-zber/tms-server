"""add_contact_number_to_users

Revision ID: 7ab8a008d2fe
Revises: e7828e95503f
Create Date: 2026-01-07 10:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ab8a008d2fe'
down_revision: Union[str, None] = 'e7828e95503f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contact_number column to users table."""
    op.add_column('users',
        sa.Column('contact_number', sa.String(50), nullable=True,
                  comment='Contact number from TMS')
    )


def downgrade() -> None:
    """Remove contact_number column from users table."""
    op.drop_column('users', 'contact_number')
