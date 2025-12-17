"""
Force users table TIMESTAMPTZ migration.
This script directly converts the users table columns to TIMESTAMPTZ.
"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def force_migration():
    """Force the users table TIMESTAMPTZ conversion."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return

    # Convert postgres:// to postgresql+asyncpg://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"🔌 Connecting to database...")
    engine = create_async_engine(database_url)

    try:
        async with engine.begin() as conn:
            # First check current state
            print("\n📊 Checking current schema...")
            result = await conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name IN ('last_synced_at', 'created_at', 'updated_at')
                ORDER BY column_name;
            """))

            rows = result.fetchall()
            print("\nCurrent schema:")
            for row in rows:
                print(f"  {row.column_name}: {row.data_type}")

            # Check if conversion is needed
            needs_conversion = any(row.data_type == 'timestamp without time zone' for row in rows)

            if not needs_conversion:
                print("\n✅ Users table already has TIMESTAMPTZ columns!")
                return

            # Run the conversion
            print("\n🔄 Converting users table to TIMESTAMPTZ...")
            await conn.execute(text("""
                ALTER TABLE users
                  ALTER COLUMN last_synced_at TYPE TIMESTAMPTZ USING last_synced_at AT TIME ZONE 'UTC',
                  ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
                  ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';
            """))

            print("✅ Conversion complete!")

            # Verify
            print("\n📊 Verifying new schema...")
            result = await conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name IN ('last_synced_at', 'created_at', 'updated_at')
                ORDER BY column_name;
            """))

            rows = result.fetchall()
            print("\nNew schema:")
            for row in rows:
                print(f"  {row.column_name}: {row.data_type}")

            print("\n✅ Migration successful!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(force_migration())
