#!/usr/bin/env python3
"""
Stress Test Data Cleanup
=========================
Deletes all stress test data seeded by seed_data.py from the database.

Removes:
- 100 stress test users (tms_user_id LIKE 'stress_tms_%')
- All conversations created by those users (CASCADE deletes messages, members,
  reactions, poll votes, message statuses, etc.)

Usage:
    cd tms-server
    python stress/setup/cleanup_staging.py

The script is idempotent — safe to run multiple times.
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

# ─── Config ────────────────────────────────────────────────────────────────────

# Environment variable takes priority (allows targeting staging/production explicitly)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    # Fall back to .env file
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL=") and "postgresql" in line:
                raw_url = line.split("=", 1)[1].strip()
                DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://")
                break

if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/tms_messaging"

# Ensure asyncpg driver
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


async def cleanup(session: AsyncSession):
    print("🧹 Starting stress test data cleanup...")

    # ── 1. Find stress test users ─────────────────────────────────────────────
    result = await session.execute(text(
        "SELECT id, tms_user_id, username FROM users WHERE tms_user_id LIKE 'stress_tms_%'"
    ))
    rows = result.fetchall()
    if not rows:
        print("  ℹ️  No stress test users found — nothing to clean up.")
        return

    user_ids = [str(row[0]) for row in rows]
    print(f"  Found {len(user_ids)} stress test users to remove")

    # ── 2. Find conversations created by stress users ─────────────────────────
    result = await session.execute(text(
        "SELECT id, name, type FROM conversations WHERE created_by = ANY(:ids)"
    ), {"ids": user_ids})
    conv_rows = result.fetchall()
    conv_ids = [str(row[0]) for row in conv_rows]
    print(f"  Found {len(conv_ids)} conversations to remove: "
          + ", ".join(f"'{row[1]}' ({row[2]})" for row in conv_rows))

    # ── 3. Delete conversations (CASCADE removes messages, members, reactions,
    #       message_statuses, poll_votes, poll_options, polls, etc.) ──────────
    if conv_ids:
        result = await session.execute(text(
            "DELETE FROM conversations WHERE id = ANY(:ids)"
        ), {"ids": conv_ids})
        print(f"  ✓ Deleted {result.rowcount} conversations (+ all cascaded data)")

    await session.commit()

    # ── 4. Delete stress test users ───────────────────────────────────────────
    result = await session.execute(text(
        "DELETE FROM users WHERE tms_user_id LIKE 'stress_tms_%'"
    ))
    deleted_users = result.rowcount
    await session.commit()
    print(f"  ✓ Deleted {deleted_users} stress test users")

    print("\n✅ Cleanup complete. Staging database is clean.")


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await cleanup(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
