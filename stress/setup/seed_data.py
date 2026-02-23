#!/usr/bin/env python3
"""
Stress Test Data Seeder
=======================
Seeds 100 test users, group conversation, polls, images, and files
directly into the DB bypassing TMS SSO for stress testing purposes.

Usage:
    cd tms-server
    python stress/setup/seed_data.py

Outputs:
    stress/data/conversation_ids.json
    stress/data/message_ids.json
    stress/data/poll_id.txt
    stress/data/user_ids.json
"""

import asyncio
import json
import uuid
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

# ─── Config ────────────────────────────────────────────────────────────────────

# Read DATABASE_URL from .env
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL=") and "postgresql" in line:
            raw_url = line.split("=", 1)[1].strip()
            # Convert sync URL to async
            DATABASE_URL = raw_url.replace("postgresql://", "postgresql+asyncpg://")
            break
else:
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tms_messaging"
    )

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

N_USERS = 100
N_EXTRA_CONVS = 10  # Additional conversations for distributed message-send test
N_IMAGE_MSGS = 100  # IMAGE-type messages in group conv
N_FILE_MSGS = 100   # FILE-type messages in group conv
N_TEXT_PER_EXTRA = 10  # TEXT messages per extra conversation

# Static 1KB test image URL (public, fast)
TEST_IMAGE_URL = "https://via.placeholder.com/1x1.png"
TEST_FILE_URL = "https://example.com/stress-test-file.pdf"


# ─── Helpers ───────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    # Return naive UTC datetime — compatible with both TIMESTAMPTZ and TIMESTAMP columns
    return datetime.utcnow()


def new_id() -> str:
    return str(uuid.uuid4())


# ─── Seeding ───────────────────────────────────────────────────────────────────

async def seed(session: AsyncSession):
    print("🌱 Starting stress test data seeding...")

    # ── 1. Create 100 test users ──────────────────────────────────────────────
    print(f"  Creating {N_USERS} test users...")
    user_ids = []
    user_tms_ids = []
    for i in range(N_USERS):
        uid = new_id()
        tms_id = f"stress_tms_{i:04d}"
        user_ids.append(uid)
        user_tms_ids.append(tms_id)
        await session.execute(text("""
            INSERT INTO users (id, tms_user_id, email, username, first_name, last_name, role, is_active, is_leader, settings_json, created_at, updated_at)
            VALUES (:id, :tms_id, :email, :username, :first, :last, 'MEMBER', true, false, :settings, :now, :now)
            ON CONFLICT (tms_user_id) DO UPDATE
                SET email = EXCLUDED.email, updated_at = EXCLUDED.updated_at
            RETURNING id
        """), {
            "id": uid,
            "tms_id": tms_id,
            "email": f"stress_user_{i:04d}@test.local",
            "username": f"stress_{i:04d}",
            "first": "Stress",
            "last": f"User{i:04d}",
            "settings": "{}",
            "now": now_utc(),
        })
    await session.commit()
    print(f"  ✓ {N_USERS} users created")

    # Re-fetch actual IDs (in case of ON CONFLICT UPDATE)
    result = await session.execute(text(
        "SELECT id FROM users WHERE tms_user_id LIKE 'stress_tms_%' ORDER BY tms_user_id"
    ))
    user_ids = [str(row[0]) for row in result.fetchall()]
    assert len(user_ids) == N_USERS, f"Expected {N_USERS} users, got {len(user_ids)}"

    # ── 2. Create group conversation ─────────────────────────────────────────
    print("  Creating group conversation with all 100 members...")
    group_conv_id = new_id()
    await session.execute(text("""
        INSERT INTO conversations (id, type, name, created_by, created_at, updated_at)
        VALUES (:id, 'group', 'Stress Test Group', :creator, :now, :now)
        ON CONFLICT DO NOTHING
    """), {"id": group_conv_id, "creator": user_ids[0], "now": now_utc()})

    for uid in user_ids:
        await session.execute(text("""
            INSERT INTO conversation_members (conversation_id, user_id, role, is_muted, joined_at)
            VALUES (:conv_id, :user_id, 'MEMBER', false, :now)
            ON CONFLICT DO NOTHING
        """), {"conv_id": group_conv_id, "user_id": uid, "now": now_utc()})
    await session.commit()
    print(f"  ✓ Group conversation created: {group_conv_id}")

    # ── 3. Create 10 extra conversations ─────────────────────────────────────
    print(f"  Creating {N_EXTRA_CONVS} extra conversations...")
    extra_conv_ids = []
    for i in range(N_EXTRA_CONVS):
        cid = new_id()
        extra_conv_ids.append(cid)
        await session.execute(text("""
            INSERT INTO conversations (id, type, name, created_by, created_at, updated_at)
            VALUES (:id, 'group', :name, :creator, :now, :now)
            ON CONFLICT DO NOTHING
        """), {"id": cid, "name": f"Stress Conv {i}", "creator": user_ids[i % N_USERS], "now": now_utc()})

        # Add first 10 users to each extra conversation
        for j in range(10):
            await session.execute(text("""
                INSERT INTO conversation_members (conversation_id, user_id, role, is_muted, joined_at)
                VALUES (:conv_id, :user_id, 'MEMBER', false, :now)
                ON CONFLICT DO NOTHING
            """), {"conv_id": cid, "user_id": user_ids[j], "now": now_utc()})
    await session.commit()
    print(f"  ✓ {N_EXTRA_CONVS} extra conversations created")

    # ── 4. Create poll in group conversation ─────────────────────────────────
    print("  Creating poll in group conversation...")
    poll_msg_id = new_id()
    poll_id = new_id()

    # Get max sequence number for group conv
    seq_result = await session.execute(text(
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM messages WHERE conversation_id = :cid"
    ), {"cid": group_conv_id})
    seq_num = seq_result.scalar()

    await session.execute(text("""
        INSERT INTO messages (id, conversation_id, sender_id, content, type, is_edited, metadata_json, sequence_number, created_at, updated_at)
        VALUES (:id, :conv_id, :sender, 'Stress test poll', 'POLL', false, '{}'::jsonb, :seq, :now, :now)
        ON CONFLICT DO NOTHING
    """), {"id": poll_msg_id, "conv_id": group_conv_id, "sender": user_ids[0], "seq": seq_num, "now": now_utc()})

    await session.execute(text("""
        INSERT INTO polls (id, message_id, question, multiple_choice, created_at)
        VALUES (:id, :msg_id, 'How is the app performing under stress?', false, :now)
        ON CONFLICT DO NOTHING
    """), {"id": poll_id, "msg_id": poll_msg_id, "now": now_utc()})

    poll_option_ids = []
    options = ["Fine - smooth as butter", "Slow - noticeable lag", "Very slow - painful", "Crashed - send help"]
    for j, opt in enumerate(options):
        oid = new_id()
        poll_option_ids.append(oid)
        await session.execute(text("""
            INSERT INTO poll_options (id, poll_id, option_text, position)
            VALUES (:id, :poll_id, :text, :pos)
            ON CONFLICT DO NOTHING
        """), {"id": oid, "poll_id": poll_id, "text": opt, "pos": j})
    await session.commit()
    print(f"  ✓ Poll created: {poll_id} with {len(options)} options")
    print(f"     Option IDs: {poll_option_ids}")

    # ── 5. Insert IMAGE messages ──────────────────────────────────────────────
    print(f"  Creating {N_IMAGE_MSGS} IMAGE messages in group conversation...")
    image_msg_ids = []
    for i in range(N_IMAGE_MSGS):
        mid = new_id()
        image_msg_ids.append(mid)
        seq_num += 1
        meta = json.dumps({
            "fileUrl": TEST_IMAGE_URL,
            "fileName": f"stress_image_{i:04d}.png",
            "fileSize": 1024,
            "mimeType": "image/png",
            "width": 100,
            "height": 100,
        })
        await session.execute(text("""
            INSERT INTO messages (id, conversation_id, sender_id, content, type, is_edited, metadata_json, sequence_number, created_at, updated_at)
            VALUES (:id, :conv_id, :sender, :content, 'IMAGE', false, CAST(:meta AS jsonb), :seq, :now, :now)
            ON CONFLICT DO NOTHING
        """), {
            "id": mid, "conv_id": group_conv_id, "sender": user_ids[i % N_USERS],
            "content": f"Stress test image {i}", "meta": meta, "seq": seq_num, "now": now_utc(),
        })
    await session.commit()
    print(f"  ✓ {N_IMAGE_MSGS} IMAGE messages created")

    # ── 6. Insert FILE messages ───────────────────────────────────────────────
    print(f"  Creating {N_FILE_MSGS} FILE messages in group conversation...")
    file_msg_ids = []
    for i in range(N_FILE_MSGS):
        mid = new_id()
        file_msg_ids.append(mid)
        seq_num += 1
        meta = json.dumps({
            "fileUrl": TEST_FILE_URL,
            "fileName": f"stress_file_{i:04d}.pdf",
            "fileSize": 102400,
            "mimeType": "application/pdf",
            "ossKey": f"stress/files/stress_file_{i:04d}.pdf",
        })
        await session.execute(text("""
            INSERT INTO messages (id, conversation_id, sender_id, content, type, is_edited, metadata_json, sequence_number, created_at, updated_at)
            VALUES (:id, :conv_id, :sender, :content, 'FILE', false, CAST(:meta AS jsonb), :seq, :now, :now)
            ON CONFLICT DO NOTHING
        """), {
            "id": mid, "conv_id": group_conv_id, "sender": user_ids[i % N_USERS],
            "content": f"Stress test file {i}", "meta": meta, "seq": seq_num, "now": now_utc(),
        })
    await session.commit()
    print(f"  ✓ {N_FILE_MSGS} FILE messages created")

    # ── 7. Insert TEXT messages in extra conversations ────────────────────────
    print(f"  Creating {N_TEXT_PER_EXTRA} TEXT messages in each extra conversation...")
    for i, cid in enumerate(extra_conv_ids):
        conv_seq = 1
        for j in range(N_TEXT_PER_EXTRA):
            mid = new_id()
            await session.execute(text("""
                INSERT INTO messages (id, conversation_id, sender_id, content, type, is_edited, metadata_json, sequence_number, created_at, updated_at)
                VALUES (:id, :conv_id, :sender, :content, 'TEXT', false, '{}'::jsonb, :seq, :now, :now)
                ON CONFLICT DO NOTHING
            """), {
                "id": mid, "conv_id": cid, "sender": user_ids[j % 10],
                "content": f"Baseline text message {j} in conv {i}", "seq": conv_seq, "now": now_utc(),
            })
            conv_seq += 1
    await session.commit()
    print(f"  ✓ {N_TEXT_PER_EXTRA * N_EXTRA_CONVS} TEXT messages created across {N_EXTRA_CONVS} conversations")

    # ── 8. Write output files ─────────────────────────────────────────────────
    all_conv_ids = [group_conv_id] + extra_conv_ids
    (DATA_DIR / "conversation_ids.json").write_text(json.dumps({
        "group_conversation_id": group_conv_id,
        "extra_conversation_ids": extra_conv_ids,
        "all_conversation_ids": all_conv_ids,
    }, indent=2))

    (DATA_DIR / "message_ids.json").write_text(json.dumps({
        "image_message_ids": image_msg_ids,
        "file_message_ids": file_msg_ids,
    }, indent=2))

    (DATA_DIR / "poll_id.txt").write_text(poll_id)
    (DATA_DIR / "poll_option_ids.json").write_text(json.dumps(poll_option_ids))

    (DATA_DIR / "user_ids.json").write_text(json.dumps({
        "user_ids": user_ids,
        "tms_user_ids": [f"stress_tms_{i:04d}" for i in range(N_USERS)],
    }, indent=2))

    print("\n✅ Seeding complete!")
    print(f"   Group conversation: {group_conv_id}")
    print(f"   Poll ID: {poll_id}")
    print(f"   Poll options: {poll_option_ids}")
    print(f"   Extra conversations: {len(extra_conv_ids)}")
    print(f"   Image messages: {len(image_msg_ids)}")
    print(f"   File messages: {len(file_msg_ids)}")
    print(f"\n   Output files written to: {DATA_DIR}/")
    print("\n⚠️  Next step: Run generate_tokens.py to create JWT tokens")


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
