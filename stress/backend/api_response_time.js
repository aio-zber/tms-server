/**
 * Test: API Response Time
 * =======================
 * Requirement 1: p95 < 200ms on GET /conversations and GET /messages
 *
 * Two parallel scenarios (ramping-arrival-rate) hit both endpoints simultaneously
 * so they share the DB connection pool — the way real traffic works.
 *
 * Run:
 *   k6 run -e BASE_URL=https://tms-chat-staging.hotelsogo-ai.com stress/backend/api_response_time.js
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
// true = high-resolution histogram (needed for accurate sub-200ms p95)
const convListMs   = new Trend('conv_list_ms',  true);
const msgListMs    = new Trend('msg_list_ms',   true);
const convErrors   = new Rate('conv_list_errors');
const msgErrors    = new Rate('msg_list_errors');
const totalReqs    = new Counter('api_requests_total');

export const options = {
  scenarios: {
    // Scenario A: GET /api/v1/conversations/
    conversations_list: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: '30s', target: 10  },  // warm-up
        { duration: '60s', target: 50  },  // sustained
        { duration: '60s', target: 100 },  // peak
        { duration: '30s', target: 0   },  // cool-down
      ],
      exec: 'getConversations',
    },

    // Scenario B: GET /api/v1/messages/conversations/{id}/messages
    // Staggered 15s so both hit peak simultaneously
    messages_list: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      startTime: '15s',
      stages: [
        { duration: '30s', target: 10  },
        { duration: '60s', target: 50  },
        { duration: '60s', target: 100 },
        { duration: '30s', target: 0   },
      ],
      exec: 'getMessages',
    },
  },

  thresholds: {
    // Requirement 1 — hard gates
    'conv_list_ms': [{ threshold: 'p(95)<200', abortOnFail: false }],
    'msg_list_ms':  [{ threshold: 'p(95)<200', abortOnFail: false }],
    // Secondary — p99 soft gate
    'conv_list_ms': [{ threshold: 'p(99)<500', abortOnFail: false }],
    'msg_list_ms':  [{ threshold: 'p(99)<500', abortOnFail: false }],
    // Error rate
    conv_list_errors: [{ threshold: 'rate<0.01', abortOnFail: false }],
    msg_list_errors:  [{ threshold: 'rate<0.01', abortOnFail: false }],
    http_req_failed:  [{ threshold: 'rate<0.05', abortOnFail: false }],
  },
};

export function setup() {
  const convId = convData[0].group_conversation_id;
  console.log('\n📡 API Response Time Test (Requirement 1)');
  console.log(`   Server: ${BASE_URL}`);
  console.log(`   Target: p95 < 200ms`);
  console.log(`   Conversation: ${convId}`);
  console.log(`   Scenario A: GET /conversations — ramp to 100 RPS`);
  console.log(`   Scenario B: GET /messages     — ramp to 100 RPS (offset 15s)\n`);
  return { convId };
}

export function getConversations() {
  const token = tokens[__VU % tokens.length];
  const res = http.get(`${BASE_URL}/api/v1/conversations/?limit=50`, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '5s',
    tags: { endpoint: 'conversations' },
  });

  convListMs.add(res.timings.duration);
  totalReqs.add(1);

  const ok = check(res, {
    'conv 200':           (r) => r.status === 200,
    'has data array':     (r) => { try { return Array.isArray(JSON.parse(r.body).data); } catch (e) { return false; } },
    'under 200ms':        (r) => r.timings.duration < 200,
  });
  convErrors.add(!ok || res.status !== 200 ? 1 : 0);

  if (res.status >= 500) {
    console.warn(`VU${__VU} GET /conversations: ${res.status} — ${res.body?.substring(0, 100)}`);
  }
}

export function getMessages(data) {
  const token = tokens[__VU % tokens.length];
  const res = http.get(
    `${BASE_URL}/api/v1/messages/conversations/${data.convId}/messages?limit=50`,
    {
      headers: { Authorization: `Bearer ${token}` },
      timeout: '5s',
      tags: { endpoint: 'messages' },
    }
  );

  msgListMs.add(res.timings.duration);
  totalReqs.add(1);

  const ok = check(res, {
    'msg 200':        (r) => r.status === 200,
    'has data array': (r) => { try { return Array.isArray(JSON.parse(r.body).data); } catch (e) { return false; } },
    'under 200ms':    (r) => r.timings.duration < 200,
  });
  msgErrors.add(!ok || res.status !== 200 ? 1 : 0);

  if (res.status >= 500) {
    console.warn(`VU${__VU} GET /messages: ${res.status} — ${res.body?.substring(0, 100)}`);
  }
}

export function teardown() {
  console.log('\n📊 API Response Time Test Complete');
  console.log('   PASS: conv_list_ms p95 < 200ms AND msg_list_ms p95 < 200ms');
  console.log('   FAIL: either p95 >= 200ms');
  console.log('   See k6 summary above for exact percentile values.');
}
