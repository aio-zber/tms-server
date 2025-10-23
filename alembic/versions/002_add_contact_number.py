"""Add contact_number to users table

Revision ID: 002_contact_number
Revises:
Create Date: 2025-10-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_contact_number'
down_revision = None  # Update this if there's a previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add contact_number column to users table
    op.add_column('users', sa.Column('contact_number', sa.String(length=50), nullable=True))

    # Create index for better performance if needed
    op.create_index(op.f('idx_users_contact_number'), 'users', ['contact_number'], unique=False)


def downgrade() -> None:
    # Drop index first
    op.drop_index(op.f('idx_users_contact_number'), table_name='users')

    # Drop column
    op.drop_column('users', 'contact_number')
