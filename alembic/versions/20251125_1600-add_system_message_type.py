"""add system message type

Revision ID: 20251125_1600
Revises: a1b2c3d4e5f6
Create Date: 2025-11-25 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251125_1600'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add SYSTEM to the message_type enum
    # First, check if the type exists and create it if not (handles edge cases)
    op.execute("""
        DO $$
        BEGIN
            -- Check if the enum type exists
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_type') THEN
                -- Create the enum type with existing values + SYSTEM
                CREATE TYPE message_type AS ENUM ('TEXT', 'IMAGE', 'FILE', 'VOICE', 'POLL', 'CALL', 'SYSTEM');
            ELSE
                -- Add SYSTEM value if the type exists (PostgreSQL 9.1+)
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumlabel = 'SYSTEM'
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'message_type')
                ) THEN
                    ALTER TYPE message_type ADD VALUE 'SYSTEM';
                END IF;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values
    # This would require recreating the enum type and migrating data
    # For safety, we leave SYSTEM in the enum
    pass
