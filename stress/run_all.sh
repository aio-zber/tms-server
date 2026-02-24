#!/usr/bin/env bash
# ============================================================
# TMS Chat — Full Performance Test Suite
# ============================================================
# Covers all 6 testable requirements from Requirements.md:
#   1. API Response Time       — p95 < 200ms
#   2. WebSocket Latency       — roundtrip < 100ms
#   3. Database Query Time     — p95 < 100ms (pg_stat_statements)
#   4. File Upload             — 100MB support
#   5. Concurrent Users        — 0 → 3000 WebSocket connections
#   6. Message Throughput      — find actual msgs/sec ceiling
#   7. Uptime                  — not testable in a session (skip)
#
# Usage:
#   cd tms-server
#   BASE_URL=https://tms-chat-staging.hotelsogo-ai.com \
#   DATABASE_URL_SYNC=postgresql://postgres:pass@host:5432/db \
#   NEXTAUTH_SECRET=<secret> \
#     bash stress/run_all.sh
#
# Skip flags:
#   SKIP_WS=1        skip WebSocket test (Requirements 2 + 5)
#   SKIP_UPLOAD=1    skip 100MB upload test (Requirement 4)
#   SKIP_THROUGHPUT=1 skip throughput ceiling test (Requirement 6)
#   FORCE_RESEED=1   wipe and re-seed test data
#   FILE_SIZE_MB=10  use smaller file for quick smoke test (default: 100)
# ============================================================

set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────────

BASE_URL="${BASE_URL:-https://tms-chat-staging.hotelsogo-ai.com}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "${SCRIPT_DIR}")"
DATA_DIR="${SCRIPT_DIR}/data"
RESULTS_DIR="${SCRIPT_DIR}/results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${RESULTS_DIR}"

echo "============================================================"
echo "TMS Chat Stress Test Suite"
echo "============================================================"
echo "  Server:    ${BASE_URL}"
echo "  Timestamp: ${TIMESTAMP}"
echo "  Results:   ${RESULTS_DIR}"
echo ""

# ─── Step 0: Check dependencies ────────────────────────────────────────────────

echo "=== Step 0: Dependency Check ==="

if ! command -v k6 &>/dev/null; then
  echo "❌ k6 not found. Install: https://k6.io/docs/getting-started/installation/"
  exit 1
fi
echo "  ✅ k6 $(k6 version 2>&1 | head -1)"

if ! command -v node &>/dev/null; then
  echo "❌ node not found. Install Node.js 18+"
  exit 1
fi
echo "  ✅ node $(node --version)"

# Install socket.io-client if needed
if [ ! -d "${SCRIPT_DIR}/websocket/node_modules" ]; then
  echo "  Installing socket.io-client..."
  cd "${SCRIPT_DIR}/websocket" && npm install --silent && cd "${SCRIPT_DIR}"
fi
echo "  ✅ socket.io-client ready"

# Raise OS file descriptor limit for WebSocket test
ulimit -n 65535 2>/dev/null || true
FD_LIMIT=$(ulimit -n)
echo "  File descriptor limit: ${FD_LIMIT}"
if [ "${FD_LIMIT}" -lt 10000 ]; then
  echo "  ⚠️  Low FD limit — WebSocket test may fail at high connection counts."
  echo "     Run: ulimit -n 65535 before this script."
fi

# ─── Step 1: Health check ──────────────────────────────────────────────────────

echo ""
echo "=== Step 1: Health Check ==="

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health/ready" || echo "000")
if [ "${HTTP_STATUS}" != "200" ]; then
  echo "❌ Server at ${BASE_URL} returned HTTP ${HTTP_STATUS}. Is it running?"
  exit 1
fi
echo "  ✅ Server healthy (HTTP 200)"

# ─── Step 2: Seed data ─────────────────────────────────────────────────────────

echo ""
echo "=== Step 2: Test Data Setup ==="

cd "${SERVER_DIR}"

if [ "${FORCE_RESEED:-0}" = "1" ]; then
  echo "  FORCE_RESEED=1 — cleaning and re-seeding..."
  DATABASE_URL="${DATABASE_URL:-}" python3 stress/setup/cleanup_staging.py || true
  DATABASE_URL="${DATABASE_URL:-}" python3 stress/setup/seed_data.py
  NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-}" python3 stress/setup/generate_tokens.py
elif [ ! -f "${DATA_DIR}/tokens_array.json" ] || [ ! -f "${DATA_DIR}/conversation_ids.json" ]; then
  echo "  Data files missing — seeding now..."
  DATABASE_URL="${DATABASE_URL:-}" python3 stress/setup/seed_data.py
  NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-}" python3 stress/setup/generate_tokens.py
else
  echo "  ✅ Data files exist (use FORCE_RESEED=1 to regenerate)"
fi

# Extract IDs for scripts that need -e flags
CONV_ID=$(python3 -c "import json; print(json.load(open('${DATA_DIR}/conversation_ids.json'))['group_conversation_id'])")
POLL_ID=$(cat "${DATA_DIR}/poll_id.txt")
echo "  Group conversation: ${CONV_ID}"
echo "  Poll:               ${POLL_ID}"

cd "${SCRIPT_DIR}"

# ─── Helpers ──────────────────────────────────────────────────────────────────

run_k6() {
  local label="$1"; shift
  local script="$1"; shift
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ${label}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  k6 run \
    -e "BASE_URL=${BASE_URL}" \
    --out "json=${RESULTS_DIR}/${label}_${TIMESTAMP}.json" \
    "$@" \
    "${SCRIPT_DIR}/${script}" \
    && echo "  ✅ ${label} — all thresholds passed" \
    || echo "  ⚠️  ${label} — some thresholds failed (see above)"
}

# ─── Step 3: Requirement 1 — API Response Time ─────────────────────────────────

run_k6 "req1_api_response_time" "backend/api_response_time.js"

# ─── Step 4: Requirements 2 + 5 — WebSocket (roundtrip + concurrent) ──────────

if [ "${SKIP_WS:-0}" != "1" ]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  req2_req5_websocket (Roundtrip + 3000 Concurrent Connections)"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  BASE_URL="${BASE_URL}" \
  MAX_CONNECTIONS="${MAX_CONNECTIONS:-3000}" \
    node --max-old-space-size=4096 "${SCRIPT_DIR}/websocket/connections.js" \
    2>&1 | tee "${RESULTS_DIR}/req2_req5_websocket_${TIMESTAMP}.log"
else
  echo ""
  echo "  ⏭️  Skipping WebSocket test (SKIP_WS=1)"
fi

# ─── Step 5: Advisory lock validation (covers DB indirectly) ──────────────────

run_k6 "req_advisory_lock" "backend/message_send.js"

# ─── Step 6: Requirement 6 — Message Throughput Ceiling ───────────────────────

if [ "${SKIP_THROUGHPUT:-0}" != "1" ]; then
  echo ""
  echo "  ℹ️  Throughput test: for accurate ceiling, temporarily set"
  echo "     RATE_LIMIT_PER_MINUTE=100000 on the staging server."
  run_k6 "req6_message_throughput" "backend/message_throughput.js"
else
  echo ""
  echo "  ⏭️  Skipping throughput test (SKIP_THROUGHPUT=1)"
fi

# ─── Step 7: Poll voting (validates optimistic lock fix) ──────────────────────

run_k6 "poll_vote" "backend/poll_vote.js" -e "POLL_ID=${POLL_ID}"

# Reset poll votes for repeatability
if [ -n "${DATABASE_URL_SYNC:-}" ]; then
  echo "  Resetting poll votes..."
  psql "${DATABASE_URL_SYNC}" -c \
    "DELETE FROM poll_votes WHERE option_id IN (SELECT id FROM poll_options WHERE poll_id='${POLL_ID}')" \
    2>/dev/null && echo "  ✅ Poll votes cleared" || echo "  ⚠️  Could not reset poll votes"
fi

# ─── Step 8: Reactions ────────────────────────────────────────────────────────

run_k6 "reactions" "backend/reactions.js" -e "CONV_ID=${CONV_ID}"

# ─── Step 9: Media messages (read-heavy) ─────────────────────────────────────

run_k6 "media_messages" "backend/media_messages.js" -e "CONV_ID=${CONV_ID}"

# ─── Step 10: File listing (read-heavy) ──────────────────────────────────────

run_k6 "file_listing" "backend/file_listing.js" -e "CONV_ID=${CONV_ID}"

# ─── Step 11: Requirement 4 — File Upload (100MB) ────────────────────────────

if [ "${SKIP_UPLOAD:-0}" != "1" ]; then
  # Pre-generate 100MB binary if not present (avoids JS heap allocation)
  if [ ! -f "${DATA_DIR}/test_100mb.bin" ]; then
    echo ""
    echo "  Generating test_100mb.bin (${FILE_SIZE_MB:-100}MB)..."
    dd if=/dev/urandom of="${DATA_DIR}/test_100mb.bin" \
       bs=1M count="${FILE_SIZE_MB:-100}" 2>/dev/null \
      && echo "  ✅ test_100mb.bin ready" \
      || echo "  ⚠️  dd failed — file_upload.js will use in-memory buffer"
  fi

  run_k6 "req4_file_upload" "backend/file_upload.js" \
    -e "FILE_SIZE_MB=${FILE_SIZE_MB:-100}" \
    -e "FILE_FROM_DISK=1"
else
  echo ""
  echo "  ⏭️  Skipping file upload test (SKIP_UPLOAD=1)"
fi

# ─── Step 12: Requirement 3 — DB Query Times ─────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  req3_db_query_time (pg_stat_statements)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "${DATABASE_URL_SYNC:-}" ]; then
  psql "${DATABASE_URL_SYNC}" \
       -f "${SCRIPT_DIR}/monitoring/pg_stat_statements.sql" \
    2>&1 | tee "${RESULTS_DIR}/req3_db_query_time_${TIMESTAMP}.log" \
    && echo "  ✅ DB stats written to results" \
    || echo "  ⚠️  psql failed — is pg_stat_statements installed? (CREATE EXTENSION IF NOT EXISTS pg_stat_statements)"
else
  echo "  ⚠️  DATABASE_URL_SYNC not set — skipping DB query time analysis"
  echo "     Set DATABASE_URL_SYNC=postgresql://user:pass@host:5432/db and re-run"
  echo "     Or run manually: psql \$DATABASE_URL_SYNC -f stress/monitoring/pg_stat_statements.sql"
fi

# ─── Final Summary ────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  ALL TESTS COMPLETE"
echo "============================================================"
echo "  Results directory: ${RESULTS_DIR}/"
echo ""
ls -lah "${RESULTS_DIR}/"*"${TIMESTAMP}"* 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'

echo ""
echo "  Requirement coverage:"
echo "    Req 1 — API p95 < 200ms       → req1_api_response_time_*.json"
echo "    Req 2 — WS roundtrip < 100ms  → req2_req5_websocket_*.log"
echo "    Req 3 — DB p95 < 100ms        → req3_db_query_time_*.log"
echo "    Req 4 — 100MB upload          → req4_file_upload_*.json"
echo "    Req 5 — 3000 concurrent WS    → req2_req5_websocket_*.log"
echo "    Req 6 — msgs/sec ceiling      → req6_message_throughput_*.json"
echo "    Req 7 — 99.9% uptime          → not testable in a session"
echo ""
echo "  To interpret results, check the VERDICT lines in each log"
echo "  and compare against Requirements.md targets."
echo "============================================================"
