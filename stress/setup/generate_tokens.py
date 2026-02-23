#!/usr/bin/env python3
"""
JWT Token Generator for Stress Tests
=====================================
Reads seeded user_ids.json and generates 100 valid JWT tokens
that match the NextAuth/TMS token format expected by the server.

Usage:
    cd tms-server
    python stress/setup/generate_tokens.py

Output:
    stress/data/tokens.json
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import jwt
except ImportError:
    print("❌ PyJWT not installed. Run: pip install PyJWT")
    sys.exit(1)

# ─── Config ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"

# Read secrets from .env
env_file = Path(__file__).parent.parent.parent / ".env"
NEXTAUTH_SECRET = None
JWT_SECRET = None

if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("NEXTAUTH_SECRET="):
            NEXTAUTH_SECRET = line.split("=", 1)[1].strip()
        elif line.startswith("JWT_SECRET="):
            JWT_SECRET = line.split("=", 1)[1].strip()

if not NEXTAUTH_SECRET:
    NEXTAUTH_SECRET = os.environ.get("NEXTAUTH_SECRET", "change-me-in-production")
    print(f"⚠️  NEXTAUTH_SECRET not found in .env, using: {NEXTAUTH_SECRET[:20]}...")

# The server decodes tokens using NEXTAUTH_SECRET (see security.py decode_nextauth_token)
SIGNING_SECRET = NEXTAUTH_SECRET


def generate_token(user_index: int, tms_user_id: str) -> str:
    """
    Generate a NextAuth-compatible JWT token.
    Payload matches what decode_nextauth_token() expects:
        required fields: id, email, exp, iat
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=720)  # 30 days — matches JWT_EXPIRATION_HOURS

    payload = {
        "id": tms_user_id,
        "email": f"stress_user_{user_index:04d}@test.local",
        "name": f"Stress User{user_index:04d}",
        "role": "MEMBER",
        "hierarchyLevel": "staff",
        "image": None,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(payload, SIGNING_SECRET, algorithm="HS256")
    # PyJWT >= 2.0 returns str directly
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def main():
    # Load seeded user data
    user_ids_file = DATA_DIR / "user_ids.json"
    if not user_ids_file.exists():
        print("❌ user_ids.json not found. Run seed_data.py first.")
        sys.exit(1)

    data = json.loads(user_ids_file.read_text())
    tms_ids = data["tms_user_ids"]
    db_ids = data["user_ids"]

    print(f"🔑 Generating {len(tms_ids)} JWT tokens...")

    tokens = []
    for i, tms_id in enumerate(tms_ids):
        token = generate_token(i, tms_id)
        tokens.append({
            "index": i,
            "tms_user_id": tms_id,
            "db_user_id": db_ids[i],
            "email": f"stress_user_{i:04d}@test.local",
            "token": token,
        })

    output_file = DATA_DIR / "tokens.json"
    output_file.write_text(json.dumps(tokens, indent=2))

    # Also write just the token strings for k6 (SharedArray format)
    token_strings = [t["token"] for t in tokens]
    (DATA_DIR / "tokens_array.json").write_text(json.dumps(token_strings))

    print(f"✅ {len(tokens)} tokens written to {output_file}")
    print(f"   Token sample (first): {tokens[0]['token'][:80]}...")
    print(f"\n   tokens.json        — full info (index, tms_id, db_id, email, token)")
    print(f"   tokens_array.json  — just token strings (for k6 SharedArray)")


if __name__ == "__main__":
    main()
