"""
One-time script to re-sync all users from GCGC to populate firstName/lastName.

Run this after deploying the updated user_repo.py fix.

Usage:
    python sync_users_from_gcgc.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_db
from app.repositories.user_repo import UserRepository
from app.core.tms_client import tms_client
from sqlalchemy import select
from app.models.user import User


async def sync_all_users():
    """Re-sync all existing users from GCGC."""
    print("🔄 Starting user re-sync from GCGC...")

    async for db in get_db():
        try:
            user_repo = UserRepository(db)

            # Get all users
            result = await db.execute(select(User))
            users = result.scalars().all()

            print(f"📊 Found {len(users)} users to sync")

            synced = 0
            failed = 0

            for user in users:
                try:
                    print(f"\n👤 Syncing user: {user.tms_user_id} ({user.email})")

                    # Fetch fresh data from GCGC
                    tms_data = await tms_client.get_user_by_id_with_api_key(
                        user.tms_user_id,
                        use_cache=False  # Force fresh fetch
                    )

                    print(f"   📥 GCGC data: name='{tms_data.get('name')}', "
                          f"firstName='{tms_data.get('firstName')}', "
                          f"lastName='{tms_data.get('lastName')}'")

                    # Re-sync user (will use new logic to handle name field)
                    updated_user = await user_repo.upsert_from_tms(
                        user.tms_user_id,
                        tms_data
                    )

                    print(f"   ✅ Updated: first_name='{updated_user.first_name}', "
                          f"last_name='{updated_user.last_name}'")

                    synced += 1

                except Exception as e:
                    print(f"   ❌ Failed to sync {user.tms_user_id}: {e}")
                    failed += 1
                    continue

            await db.commit()

            print(f"\n\n{'='*60}")
            print(f"✅ Sync complete!")
            print(f"   Synced: {synced}")
            print(f"   Failed: {failed}")
            print(f"{'='*60}")

        except Exception as e:
            print(f"❌ Fatal error: {e}")
            await db.rollback()
            raise
        finally:
            break  # Only use first db session


if __name__ == "__main__":
    asyncio.run(sync_all_users())
