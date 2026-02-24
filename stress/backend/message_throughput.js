/**
 * Test: Message Throughput Ceiling
 * ==================================
 * Requirement 6: find the actual sustained messages/second ceiling.
 *
 * Uses constant-arrival-rate executor: fires exactly N requests/sec regardless
 * of how long each takes. When the server saturates, the error rate rises —
 * that RPS level is the ceiling.
 *
 * Stage 1 (calibration): 30 msg/s × 60s — must pass cleanly.
 * Stage 2 (ceiling probe): ramp 50 → 300 msg/s — watch error rate climb.
 *
 * IMPORTANT: The server has a 30/min per-user rate limit. To bypass it for
 * an accurate ceiling measurement, temporarily set RATE_LIMIT_PER_MINUTE=100000
 * on the staging server before running this test.
 *
 * Run:
 *   k6 run -e BASE_URL=https://tms-chat-staging.hotelsogo-ai.com stress/backend/message_throughput.js
 */

import http from 'k6/http';
import { check } from 'k6';
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
const rateLimited   = new Counter('throughput_messages_rate_limited');  // 429s

export const options = {
  scenarios: {
    // Stage 1: Baseline calibration — 30 msg/s must succeed
    calibration: {
      executor: 'constant-arrival-rate',
      rate: 30,
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 40,
      maxVUs: 100,
      exec: 'sendMessage',
      gracefulStop: '5s',
    },

    // Stage 2: Ceiling probe — ramp 50 → 300 msg/s
    // The point where error rate > 5% is the practical throughput ceiling.
    ceiling_probe: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 500,
      startTime: '70s',
      stages: [
        { duration: '30s', target: 100 },  // warm-up
        { duration: '60s', target: 200 },  // moderate stress
        { duration: '60s', target: 300 },  // high stress
        { duration: '30s', target: 50  },  // cool-down
      ],
      exec: 'sendMessage',
      gracefulStop: '10s',
    },
  },

  thresholds: {
    // Calibration must stay clean at 30 msg/s
    'throughput_send_ms{scenario:calibration}': [
      { threshold: 'p(95)<1000', abortOnFail: false },
    ],
    // Soft error-rate gate — we WANT to find the ceiling, not abort
    throughput_send_errors: [{ threshold: 'rate<0.30', abortOnFail: false }],
    http_req_failed:        [{ threshold: 'rate<0.20', abortOnFail: false }],
  },
};

export function setup() {
  const convIds = convData[0].extra_conversation_ids;
  const groupId = convData[0].group_conversation_id;
  const ids = (convIds && convIds.length > 0) ? convIds : [groupId];

  console.log('\n🚀 Message Throughput Test (Requirement 6)');
  console.log(`   Server: ${BASE_URL}`);
  console.log(`   Goal: find sustained msgs/sec ceiling`);
  console.log(`   Stage 1 (calibration): 30 msg/s × 60s`);
  console.log(`   Stage 2 (ceiling probe): ramp 50 → 300 msg/s`);
  console.log(`   Conversations: ${ids.length} (distributed to avoid lock contention)`);
  console.log(`   ⚠️  Set RATE_LIMIT_PER_MINUTE=100000 on server to bypass 30/min user limit\n`);

  return { convIds: ids };
}

export function sendMessage(data) {
  const vuIdx   = __VU % tokens.length;
  const token   = tokens[vuIdx];
  // Round-robin across conversations to spread advisory lock contention
  const convIdx = (__VU + __ITER) % data.convIds.length;
  const convId  = data.convIds[convIdx];

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
    timeout: '8s',
  });

  sendMs.add(res.timings.duration);

  if (res.status === 200 || res.status === 201) {
    accepted.add(1);
    sendErrors.add(0);
  } else if (res.status === 429) {
    // Rate-limited — not a server error, tracks separately
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
}

export function teardown() {
  console.log('\n📊 Message Throughput Test Complete');
  console.log('   throughput_messages_accepted   = total successful sends');
  console.log('   throughput_messages_rate_limited = 429s (per-user rate cap)');
  console.log('   throughput_send_errors         = 5xx / network failures');
  console.log('');
  console.log('   To compute ceiling:');
  console.log('     calibration msgs/s ≈ throughput_messages_accepted (stage 1) / 60');
  console.log('     ceiling = lowest RPS where throughput_send_errors rate > 5%');
  console.log('     (visible in the ceiling_probe scenario metrics over time)');
  console.log('');
  console.log('   If 429s dominate: run with RATE_LIMIT_PER_MINUTE=100000 on server.');
}
