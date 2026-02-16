"""merge_contact_number_and_e2ee_branches

Revision ID: 9853d58ad1e4
Revises: a3f7c8d91b2e
Create Date: 2026-02-16 14:24:35.094801

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9853d58ad1e4'
down_revision: Union[str, None] = 'a3f7c8d91b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
