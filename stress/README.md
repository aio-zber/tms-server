# TMS Chat Application — Stress Test Suite

Comprehensive performance stress tests for `tms-server` (FastAPI + PostgreSQL + Redis) and `tms-client` (Next.js 14).

## Pre-Identified Bottlenecks

Before running any tests, static code analysis confirmed four bottlenecks:

| # | Location | Severity | Issue |
|---|----------|----------|-------|
| 1 | `app/repositories/message_repo.py:164–182` | **CRITICAL** | Debug query: unbounded `SELECT *` with no LIMIT — doubles DB load on every message fetch |
| 2 | `app/services/poll_service.py:194` | **HIGH** | `with_for_update()` serializes all concurrent voters — pool exhausts at 31+ VUs |
| 3 | `src/features/messaging/components/MessageList.tsx:332` | **HIGH** | No DOM virtualization — `react-window` installed but unused, 200 messages = 200 full DOM trees |
| 4 | `src/features/messaging/hooks/useMessagesQuery.ts:~93` | **MEDIUM** | Sequential decryption loop (correct for Double Ratchet, but E2EE adds latency) |

---

## Directory Structure

```
stress/
├── setup/
│   ├── seed_data.py          # Insert 100 users, conversations, messages, poll
│   └── generate_tokens.py    # Create tokens.json array of 100 JWTs
├── data/                     # Generated at runtime (gitignored)
│   ├── tokens_array.json     # 100 JWT token strings
│   ├── tokens.json           # Full token info (index, tms_id, email, token)
│   ├── conversation_ids.json # Group + 10 extra conversation UUIDs
│   ├── message_ids.json      # 100 image + 100 file message UUIDs
│   ├── poll_id.txt           # Single poll UUID
│   ├── poll_option_ids.json  # 4 poll option UUIDs
│   └── user_ids.json         # 100 test user DB IDs + TMS IDs
├── backend/
│   ├── poll_vote.js          # k6: concurrent poll voting (tests with_for_update lock)
│   ├── reactions.js          # k6: reaction write + read stress
│   ├── media_messages.js     # k6: IMAGE-heavy conversation fetch
│   ├── file_listing.js       # k6: FILE-heavy conversation fetch
│   └── message_send.js       # k6: message send advisory lock (single vs distributed)
├── websocket/
│   └── connections.js        # Node.js: Socket.IO connection storm (200 concurrent)
├── browser/
│   └── media_render.js       # Playwright: FPS, DOM size, heap, LCP
├── monitoring/
│   └── pg_queries.sql        # Live PostgreSQL diagnostics
└── results/                  # Created at runtime — JSON results per test
```

---

## Prerequisites

### Install k6
```bash
# Linux
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# macOS
brew install k6

# Or via npm (no sudo needed)
npm install -g k6
```

### Install WebSocket test dependencies
```bash
cd tms-server/stress/websocket
npm init -y
npm install socket.io-client
```

### Install Playwright (optional, for browser tests)
```bash
cd tms-client
npm install -D playwright
npx playwright install chromium
```

---

## Execution Guide

### Step 0: Start the server
```bash
cd tms-server
uvicorn app.main:app --reload --port 8000
```

### Step 1: Seed test data
```bash
cd tms-server
python stress/setup/seed_data.py
python stress/setup/generate_tokens.py
```

This creates all files in `stress/data/`.

### Step 2: Get IDs for test runs
```bash
POLL_ID=$(cat stress/data/poll_id.txt)
CONV_ID=$(python -c "import json; print(json.load(open('stress/data/conversation_ids.json'))['group_conversation_id'])")
echo "Poll: $POLL_ID"
echo "Conv: $CONV_ID"
```

### Step 3: Optional — disable rate limiting for tests
```bash
export RATE_LIMIT_PER_MINUTE=100000
```

### Step 4: Run health check
```bash
curl http://localhost:8000/health/ready
# Expected: {"database": true, "redis": true}
```

---

## Running Individual Tests

### Test A: Poll Concurrent Voting
```bash
# Ramp test (0 → 100 VUs)
k6 run -e POLL_ID=$POLL_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/poll_vote_$(date +%s).json \
  stress/backend/poll_vote.js

# Reset votes between runs
psql -d tms_messaging -c "DELETE FROM poll_votes WHERE option_id IN (SELECT id FROM poll_options WHERE poll_id='$POLL_ID')"
```

**Monitor in parallel terminal:**
```bash
watch -n 1 "psql -d tms_messaging -c \"SELECT count(*) as waiting FROM pg_stat_activity WHERE wait_event_type='Lock' AND datname='tms_messaging'\""
```

### Test B: Reactions
```bash
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/reactions_$(date +%s).json \
  stress/backend/reactions.js
```

### Test C: Media Messages
```bash
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/media_$(date +%s).json \
  stress/backend/media_messages.js
```

### Test D: File Listing
```bash
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/files_$(date +%s).json \
  stress/backend/file_listing.js
```

### Test E: Message Send (Advisory Lock)
```bash
k6 run -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/msg_send_$(date +%s).json \
  stress/backend/message_send.js
```

### WebSocket Connections
```bash
cd stress/websocket
node connections.js
```

### Browser Performance (Playwright)
```bash
CONV_ID=$CONV_ID \
AUTH_TOKEN=$(python -c "import json; print(json.load(open('stress/data/tokens_array.json'))[0])") \
CLIENT_URL=http://localhost:3000 \
  node stress/browser/media_render.js
```

---

## Full Test Run (Sequential)

```bash
#!/bin/bash
set -e

cd tms-server

# Get IDs
POLL_ID=$(cat stress/data/poll_id.txt)
CONV_ID=$(python -c "import json; print(json.load(open('stress/data/conversation_ids.json'))['group_conversation_id'])")
TOKEN=$(python -c "import json; print(json.load(open('stress/data/tokens_array.json'))[0])")

echo "=== Health Check ==="
curl -s http://localhost:8000/health/ready | python -m json.tool

echo "=== Test A: WebSocket (safest, no mutations) ==="
cd stress/websocket && node connections.js && cd ../..

echo "=== Test B: Message Send ==="
k6 run -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/msg_send_$(date +%s).json \
  stress/backend/message_send.js

echo "=== Test C: Poll Votes (ramp) ==="
k6 run -e POLL_ID=$POLL_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/poll_vote_$(date +%s).json \
  stress/backend/poll_vote.js

echo "Resetting poll votes..."
psql -d tms_messaging -c "DELETE FROM poll_votes WHERE option_id IN (SELECT id FROM poll_options WHERE poll_id='$POLL_ID')"

echo "=== Test D: Reactions ==="
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/reactions_$(date +%s).json \
  stress/backend/reactions.js

echo "=== Test E: Media Messages ==="
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/media_$(date +%s).json \
  stress/backend/media_messages.js

echo "=== Test F: File Listing ==="
k6 run -e CONV_ID=$CONV_ID -e BASE_URL=http://localhost:8000 \
  --out json=stress/results/files_$(date +%s).json \
  stress/backend/file_listing.js

echo "=== Test G: Browser Performance ==="
CONV_ID=$CONV_ID AUTH_TOKEN=$TOKEN CLIENT_URL=http://localhost:3000 \
  node stress/browser/media_render.js

echo ""
echo "=== All tests complete. Results in stress/results/ ==="
ls -la stress/results/
```

---

## Verdict Decision Matrix

| Verdict | Criteria |
|---------|---------|
| **Fine** ✅ | p95 latency < 2× baseline at 100 VUs; error rate < 1% |
| **Slows Down** ⚠️ | p95 latency 2–10× baseline; error rate 1–10%; no crashes |
| **Crashes** ❌ | Error rate > 10%; 5xx responses; pool exhaustion; server restart needed |

---

## Expected Findings

| Test | Expected Verdict | Root Cause |
|------|-----------------|------------|
| Poll voting @ ≤15 VUs | ✅ Fine | Lock queue empty |
| Poll voting @ 16-30 VUs | ⚠️ Slows Down | Lock queue builds |
| Poll voting @ 31+ VUs | ❌ Crashes | DB pool exhausted |
| Reactions (write) | ✅ Fine | No locking |
| Reactions (read, 100 reactions/msg) | ⚠️ Slows Down | selectinload loads thousands of rows |
| Media fetch (50 VUs) | ⚠️ Slows Down | Debug query doubles DB load |
| File listing (30 VUs) | ⚠️ Slows Down | Debug query + HMAC per file |
| WebSocket (200 connections) | ⚠️ Slows Down | 200 DB queries at connect time |
| Browser (50 messages) | ✅ Fine | DOM manageable |
| Browser (150 messages) | ❌ Crashes | No virtualization, FPS tanks |

---

## Recommended Fixes (After Testing)

### Fix 1: Remove Debug Query (CRITICAL)
**File**: `app/repositories/message_repo.py:164–182`
```python
# DELETE these lines entirely:
debug_query = (
    select(Message)
    .where(Message.conversation_id == conversation_id)
)
# ... entire debug block ...
```
**Impact**: Reduces every message fetch from 2 queries to 1. ~50% DB load reduction.

### Fix 2: Poll Lock (HIGH)
**File**: `app/services/poll_service.py:194`

Option A — Optimistic locking with retry (eliminates blocking):
```python
# Replace with_for_update() with optimistic retry
from asyncio import sleep as async_sleep

for attempt in range(3):
    result = await self.db.execute(
        select(Poll).where(Poll.id == poll_id)
    )
    poll = result.scalar_one_or_none()
    # ... validate ... insert vote ...
    try:
        await self.db.commit()
        break
    except IntegrityError:
        await self.db.rollback()
        await async_sleep(0.05 * (attempt + 1))
```

Option B — Pre-aggregate vote counts in Redis (eliminates DB contention entirely):
```python
# INCR poll:{poll_id}:option:{option_id}:count in Redis
# Sync to DB every 5s via background task
```

### Fix 3: Virtualize Message List (HIGH)
**File**: `src/features/messaging/components/MessageList.tsx:332`

`react-window` is already in `package.json`. Replace `validMessages.map()` with:
```tsx
import { VariableSizeList } from 'react-window';

<VariableSizeList
  height={containerHeight}
  itemCount={validMessages.length}
  itemSize={getMessageHeight}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>
      <MessageBubble message={validMessages[index]} ... />
    </div>
  )}
</VariableSizeList>
```

### Fix 4: Pre-aggregate Reactions (MEDIUM)
Store reaction counts in a summary column instead of loading all rows:
```python
# Add to messages table:
# reaction_counts JSONB DEFAULT '{}'
# Update on reaction add/remove: {"👍": 5, "❤️": 3}
```
