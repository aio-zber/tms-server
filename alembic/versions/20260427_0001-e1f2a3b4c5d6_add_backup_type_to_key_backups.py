"""add backup_type to key_backups

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-04-27 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'key_backups',
        sa.Column('backup_type', sa.String(16), nullable=False, server_default='pin'),
    )


def downgrade() -> None:
    op.drop_column('key_backups', 'backup_type')
