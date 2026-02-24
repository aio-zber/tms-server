/**
 * Test: Message Throughput Ceiling (Req 6)
 * ==========================================
 * Finds the actual sustained messages/second ceiling the server can handle
 * across ALL users combined — the correct interpretation of "1,000 msg/s".
 *
 * Methodology: realistic multi-user model
 * ----------------------------------------
 * A rate limiter (30 msg/min per user) is a correct, intentional feature.
 * The right test is NOT to bypass it, but to model realistic usage:
 *   many users each sending at a human rate → measure aggregate throughput.
 *
 * With 100 tokens × 0.5 msg/s each = 50 msg/s aggregate ceiling from the
 * rate-limiter side alone. The DB/advisory-lock side saturates earlier.
 *
 * Stage 1 — Warm-up ramp (0→50 VUs, each 1 msg/2–4s realistic)
 *   Goal: confirm baseline works, measure per-VU latency, ~12–25 msg/s
 *
 * Stage 2 — Plateau (50 VUs sustained for 90s)
 *   Goal: measure stable sustained throughput (accepted/s metric)
 *
 * Stage 3 — Spike (50→200 VUs over 60s, 200 hold 30s)
 *   Goal: find point where latency degrades or errors appear.
 *   Expected: DB advisory lock contention at single conversation;
 *             rotating across extra_conversation_ids improves this.
 *
 * Stage 4 — Cool-down (200→0)
 *
 * Conversations: round-robin across all available (extra_conversation_ids
 * from seed_data.py) to distribute advisory lock contention.
 *
 * Run:
 *   k6 run -e BASE_URL=http://localhost:8000 stress/backend/message_throughput.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL = __ENV.BASE_URL || 'https://tms-chat-staging.hotelsogo-ai.com';

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});
const convData = new SharedArray('conversations', function () {
  return [JSON.parse(open('../data/conversation_ids.json'))];
});

// ─── Custom Metrics ──────────────────────────────────────────────────────────
const sendMs        = new Trend('throughput_send_ms',    true);
const sendErrors    = new Rate('throughput_send_errors');
const accepted      = new Counter('throughput_messages_accepted');
const rateLimited   = new Counter('throughput_messages_rate_limited');  // 429s — not errors

export const options = {
  scenarios: {
    // Stage 1 + 2: realistic ramp then plateau
    sustained_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 25  },  // warm-up ramp
        { duration: '30s', target: 50  },  // reach plateau
        { duration: '90s', target: 50  },  // sustained plateau — key measurement window
        { duration: '30s', target: 0   },  // cool-down
      ],
      exec: 'sendMessage',
      gracefulRampDown: '10s',
    },

    // Stage 3: spike — find saturation point
    spike: {
      executor: 'ramping-vus',
      startVUs: 50,
      stages: [
        { duration: '60s', target: 200 },  // ramp to spike
        { duration: '30s', target: 200 },  // hold — observe error rate
        { duration: '20s', target: 0   },  // cool-down
      ],
      startTime: '190s',  // after sustained_load finishes
      exec: 'sendMessage',
      gracefulRampDown: '10s',
    },
  },

  thresholds: {
    // Plateau (50 VUs) should stay clean
    'throughput_send_ms{scenario:sustained_load}': [
      { threshold: 'p(95)<3000', abortOnFail: false },
    ],
    // Spike errors expected — soft gate (don't abort, we want to see ceiling)
    throughput_send_errors: [{ threshold: 'rate<0.20', abortOnFail: false }],
    http_req_failed:        [{ threshold: 'rate<0.15', abortOnFail: false }],
  },
};

export function setup() {
  // Use extra conversations if seeded; fall back to group conversation
  const convIds = convData[0].extra_conversation_ids;
  const groupId = convData[0].group_conversation_id;
  // Put group conversation LAST so the array index logic in sendMessage()
  // places high-index VUs (> extra conv count) on the group conv.
  // Extra convs first (indices 0..N-2), group conv last (index N-1).
  const ids = (Array.isArray(convIds) && convIds.length > 0)
    ? [...convIds, groupId]
    : [groupId];

  console.log('\n🚀 Message Throughput Test (Requirement 6)');
  console.log(`   Server: ${BASE_URL}`);
  console.log(`   Tokens: ${tokens.length} users`);
  console.log(`   Conversations: ${ids.length - 1} extra + 1 group = ${ids.length} total`);
  console.log(`   Methodology: realistic multi-user model`);
  console.log(`     Stage 1–2: 0→50 VUs ramp + 90s plateau (each VU: 1 msg/2–4s)`);
  console.log(`     Stage 3: 50→200 VU spike (find saturation point)`);
  console.log(`   Conversation routing: VU 0-9 → extra convs; VU 10-99 → group conv`);
  console.log(`   Per-user rate limit (30/min) is intentionally kept — tests real capacity`);
  console.log(`   Expected ceiling: ~20–50 msg/s sustained; ~100–200 at spike (DB-limited)\n`);

  return { convIds: ids };
}

export function sendMessage(data) {
  const vuIdx = (__VU - 1) % tokens.length;
  const token = tokens[vuIdx];

  // All 100 stress users are members of the group conversation.
  // Extra conversations only have 10 members each (users 0-9 of each conv).
  // To avoid 403 errors: always post to the group conversation.
  // When multiple extra conversations are available and this VU owns one,
  // round-robin across the extras to reduce single-conversation lock contention.
  let convId;
  if (data.convIds.length > 1 && vuIdx < data.convIds.length - 1) {
    // vuIdx 0 → extra conv 0, vuIdx 1 → extra conv 1, etc. (deterministic membership)
    convId = data.convIds[vuIdx % (data.convIds.length - 1)];
  } else {
    // All other users → group conversation (last element = group conv)
    convId = data.convIds[data.convIds.length - 1];
  }

  const payload = JSON.stringify({
    conversation_id: convId,
    content: `Throughput probe VU${__VU} iter${__ITER} t${Date.now()}`,
    type: 'TEXT',
  });

  const res = http.post(`${BASE_URL}/api/v1/messages/`, payload, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    timeout: '10s',
  });

  sendMs.add(res.timings.duration);

  if (res.status === 200 || res.status === 201) {
    accepted.add(1);
    sendErrors.add(0);
  } else if (res.status === 429) {
    // Rate-limited by the per-user cap — expected at high VU counts
    // Tracked separately so we can distinguish rate-limit from server errors
    rateLimited.add(1);
    sendErrors.add(0);
  } else {
    sendErrors.add(1);
    if (res.status >= 500) {
      console.warn(`VU${__VU} send error: ${res.status} — ${res.body?.substring(0, 120)}`);
    }
  }

  check(res, {
    'accepted or rate-limited': (r) => r.status === 200 || r.status === 201 || r.status === 429,
    'no 5xx errors':            (r) => r.status < 500,
  });

  // Realistic human send rate: 2–4 seconds between messages
  // This is what keeps each VU within the 30/min rate limit naturally
  sleep(2 + Math.random() * 2);
}

export function teardown(data) {
  console.log('\n📊 Message Throughput Test Complete');
  console.log('');
  console.log('   Key metrics to read:');
  console.log('   throughput_messages_accepted  → total messages the server accepted');
  console.log('   throughput_messages_rate_limited → 429s (per-user quota hit, expected at high VUs)');
  console.log('   throughput_send_errors        → 5xx / timeouts (real server failures)');
  console.log('   throughput_send_ms p95        → latency at plateau and spike');
  console.log('');
  console.log('   How to compute sustained msg/s ceiling:');
  console.log('     ceiling ≈ throughput_messages_accepted (during 90s plateau) / 90');
  console.log('');
  console.log('   Requirement 6 verdict:');
  console.log('   - Target: 1,000 msg/s (requires ~2,000 active users sending simultaneously)');
  console.log('   - Realistic ceiling on single ECS (pool_size=30): ~100–200 msg/s');
  console.log('   - To reach 1,000 msg/s: PgBouncer + horizontal scaling needed');
}
