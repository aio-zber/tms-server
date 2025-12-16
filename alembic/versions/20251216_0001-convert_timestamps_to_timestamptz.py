"""Convert timestamp columns to TIMESTAMPTZ and fix corrupt data

Revision ID: timestamptz_001
Revises: 20241204_0001
Create Date: 2025-12-16 00:01:00.000000

This migration converts all TIMESTAMP columns to TIMESTAMPTZ (timezone-aware)
and fixes any corrupt timestamp data in the database.

Changes:
1. Identifies and fixes corrupt timestamps (NULL or future dates)
2. Converts TIMESTAMP columns to TIMESTAMPTZ (stores UTC internally)
3. Updates default values to use timezone-aware functions

This ensures:
- All timestamps are explicitly UTC
- Serialization includes timezone indicator ('Z' suffix)
- Consistent timezone handling across the application
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'timestamptz_001'
down_revision: Union[str, None] = '20241204_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade to TIMESTAMPTZ columns and fix corrupt data.

    Steps:
    1. Find and fix corrupt timestamps (NULL, future dates)
    2. Convert TIMESTAMP to TIMESTAMPTZ
    3. Update default values
    """
    # Get database connection for direct SQL execution
    connection = op.get_bind()

    print("=" * 80)
    print("TIMESTAMP TO TIMESTAMPTZ MIGRATION")
    print("=" * 80)

    # =========================
    # STEP 1: Fix Corrupt Data
    # =========================

    print("\n[STEP 1/3] Identifying and fixing corrupt timestamps...")

    # Check messages table for NULL created_at (should not exist due to NOT NULL constraint)
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM messages WHERE created_at IS NULL")
    )
    null_count = result.scalar()

    if null_count > 0:
        print(f"  ⚠️  WARNING: Found {null_count} messages with NULL created_at")
        print(f"  🔧 Fixing: Setting to CURRENT_TIMESTAMP...")
        connection.execute(
            sa.text("UPDATE messages SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        )
        print(f"  ✅ Fixed {null_count} NULL timestamps")
    else:
        print("  ✅ No NULL created_at timestamps found")

    # Check for future timestamps (likely corrupt - more than 1 hour in future)
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM messages WHERE created_at > CURRENT_TIMESTAMP + INTERVAL '1 hour'")
    )
    future_count = result.scalar()

    if future_count > 0:
        print(f"  ⚠️  WARNING: Found {future_count} messages with future timestamps")
        print(f"  🔧 Fixing: Resetting to CURRENT_TIMESTAMP...")
        connection.execute(
            sa.text(
                "UPDATE messages SET created_at = CURRENT_TIMESTAMP "
                "WHERE created_at > CURRENT_TIMESTAMP + INTERVAL '1 hour'"
            )
        )
        print(f"  ✅ Fixed {future_count} future timestamps")
    else:
        print("  ✅ No future timestamps found")

    # Check for very old timestamps (before 2020 - likely corrupt)
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM messages WHERE created_at < '2020-01-01'")
    )
    old_count = result.scalar()

    if old_count > 0:
        print(f"  ⚠️  WARNING: Found {old_count} messages with timestamps before 2020")
        print(f"  ℹ️  Keeping these as they might be intentional test data")

    # ===============================
    # STEP 2: Convert to TIMESTAMPTZ
    # ===============================

    print("\n[STEP 2/3] Converting TIMESTAMP columns to TIMESTAMPTZ...")

    # Messages table
    print("  🔄 Converting messages table...")
    op.execute("""
        ALTER TABLE messages
          ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
          ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC',
          ALTER COLUMN deleted_at TYPE TIMESTAMPTZ USING deleted_at AT TIME ZONE 'UTC';
    """)
    print("  ✅ messages table converted")

    # Message status table
    print("  🔄 Converting message_status table...")
    op.execute("""
        ALTER TABLE message_status
          ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC';
    """)
    print("  ✅ message_status table converted")

    # Message reactions table
    print("  🔄 Converting message_reactions table...")
    op.execute("""
        ALTER TABLE message_reactions
          ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';
    """)
    print("  ✅ message_reactions table converted")

    # Conversations table
    print("  🔄 Converting conversations table...")
    op.execute("""
        ALTER TABLE conversations
          ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
          ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
    """)
    print("  ✅ conversations table converted")

    # Conversation members table
    print("  🔄 Converting conversation_members table...")
    op.execute("""
        ALTER TABLE conversation_members
          ALTER COLUMN joined_at TYPE TIMESTAMPTZ USING joined_at AT TIME ZONE 'UTC',
          ALTER COLUMN last_read_at TYPE TIMESTAMPTZ USING last_read_at AT TIME ZONE 'UTC';
    """)
    print("  ✅ conversation_members table converted")

    # Calls table (if exists)
    # Check if table exists first
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'calls')"
        )
    )
    if result.scalar():
        print("  🔄 Converting calls table...")
        op.execute("""
            ALTER TABLE calls
              ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at AT TIME ZONE 'UTC',
              ALTER COLUMN ended_at TYPE TIMESTAMPTZ USING ended_at AT TIME ZONE 'UTC';
        """)
        print("  ✅ calls table converted")

    # ===================================
    # STEP 3: Update Default Values
    # ===================================

    print("\n[STEP 3/3] Updating default values...")

    # Messages table defaults
    op.execute("""
        ALTER TABLE messages
          ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """)

    # Message status defaults
    op.execute("""
        ALTER TABLE message_status
          ALTER COLUMN timestamp SET DEFAULT CURRENT_TIMESTAMP;
    """)

    # Message reactions defaults
    op.execute("""
        ALTER TABLE message_reactions
          ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """)

    # Conversations defaults
    op.execute("""
        ALTER TABLE conversations
          ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """)

    # Conversation members defaults
    op.execute("""
        ALTER TABLE conversation_members
          ALTER COLUMN joined_at SET DEFAULT CURRENT_TIMESTAMP;
    """)

    print("  ✅ Default values updated")

    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\nAll timestamp columns are now TIMESTAMPTZ (timezone-aware UTC)")
    print("Database will now serialize timestamps with 'Z' suffix (e.g., '2025-12-16T11:30:00Z')")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """
    Downgrade back to TIMESTAMP (naive) columns.

    Warning: This removes timezone information but preserves UTC timestamps.
    """
    print("=" * 80)
    print("REVERTING TIMESTAMPTZ TO TIMESTAMP")
    print("=" * 80)

    # Revert messages table
    print("\n🔄 Reverting messages table...")
    op.execute("""
        ALTER TABLE messages
          ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC',
          ALTER COLUMN updated_at TYPE TIMESTAMP USING updated_at AT TIME ZONE 'UTC',
          ALTER COLUMN deleted_at TYPE TIMESTAMP USING deleted_at AT TIME ZONE 'UTC';
    """)
    print("✅ messages table reverted")

    # Revert message_status table
    print("🔄 Reverting message_status table...")
    op.execute("""
        ALTER TABLE message_status
          ALTER COLUMN timestamp TYPE TIMESTAMP USING timestamp AT TIME ZONE 'UTC';
    """)
    print("✅ message_status table reverted")

    # Revert message_reactions table
    print("🔄 Reverting message_reactions table...")
    op.execute("""
        ALTER TABLE message_reactions
          ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC';
    """)
    print("✅ message_reactions table reverted")

    # Revert conversations table
    print("🔄 Reverting conversations table...")
    op.execute("""
        ALTER TABLE conversations
          ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC',
          ALTER COLUMN updated_at TYPE TIMESTAMP USING updated_at AT TIME ZONE 'UTC';
    """)
    print("✅ conversations table reverted")

    # Revert conversation_members table
    print("🔄 Reverting conversation_members table...")
    op.execute("""
        ALTER TABLE conversation_members
          ALTER COLUMN joined_at TYPE TIMESTAMP USING joined_at AT TIME ZONE 'UTC',
          ALTER COLUMN last_read_at TYPE TIMESTAMP USING last_read_at AT TIME ZONE 'UTC';
    """)
    print("✅ conversation_members table reverted")

    # Revert calls table (if exists)
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'calls')"
        )
    )
    if result.scalar():
        print("🔄 Reverting calls table...")
        op.execute("""
            ALTER TABLE calls
              ALTER COLUMN started_at TYPE TIMESTAMP USING started_at AT TIME ZONE 'UTC',
              ALTER COLUMN ended_at TYPE TIMESTAMP USING ended_at AT TIME ZONE 'UTC';
        """)
        print("✅ calls table reverted")

    print("\n" + "=" * 80)
    print("✅ DOWNGRADE COMPLETED")
    print("=" * 80)
    print("\nAll timestamp columns reverted to TIMESTAMP (naive, assumed UTC)")
    print("=" * 80 + "\n")
