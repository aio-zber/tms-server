/**
 * Test E: Message Send Under Advisory Lock (Bonus Test)
 * ======================================================
 * Validates that PostgreSQL advisory locks correctly serialize message sends
 * per-conversation, and that spreading load across conversations scales linearly.
 *
 * Scenario 1 (single_conversation): 50 VUs → one conversation
 *   → advisory lock serializes everything → throughput = ~1/avg_tx_time msgs/sec
 *
 * Scenario 2 (distributed_conversations): 50 VUs → 10 conversations (5 VUs each)
 *   → 10 parallel advisory locks → ~10x throughput vs. Scenario 1
 *
 * Run:
 *   k6 run -e BASE_URL=http://localhost:8000 stress/backend/message_send.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});

const convData = new SharedArray('conversations', function () {
  // SharedArray requires an array; wrap the object in one
  return [JSON.parse(open('../data/conversation_ids.json'))];
});

// ─── Custom Metrics ─────────────────────────────────────────────────────────────

const singleConvLatency = new Trend('single_conv_send_ms', true);
const distributedLatency = new Trend('distributed_send_ms', true);
const sendErrors = new Rate('send_errors');
const messagesSent = new Counter('messages_sent_total');

export const options = {
  scenarios: {
    // 50 VUs all hammering ONE conversation
    single_conversation: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
      exec: 'sendToSingleConversation',
    },

    // 50 VUs spread across 10 conversations (5 per conv)
    distributed_conversations: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
      startTime: '70s',
      exec: 'sendToDistributedConversations',
    },
  },

  thresholds: {
    'single_conv_send_ms': [{ threshold: 'p(95)<3000', abortOnFail: false }],
    'distributed_send_ms': [{ threshold: 'p(95)<1000', abortOnFail: false }],
    send_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

export function setup() {
  const groupConvId = convData[0].group_conversation_id;
  const extraConvIds = convData[0].extra_conversation_ids;

  console.log('\n✉️  Message Send Advisory Lock Test');
  console.log(`   Single conv: 50 VUs → ${groupConvId}`);
  console.log(`   Distributed: 50 VUs → 10 conversations`);
  console.log(`   Expected: distributed ~10x faster than single\n`);

  return {
    groupConvId,
    extraConvIds: extraConvIds.slice(0, 10),
  };
}

export function sendToSingleConversation(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  const payload = JSON.stringify({
    conversation_id: data.groupConvId,
    content: `Stress test message from VU${__VU} at ${Date.now()}`,
    type: 'TEXT',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    timeout: '10s',
  };

  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/api/v1/messages/`,
    payload,
    params
  );
  const elapsed = Date.now() - start;

  singleConvLatency.add(elapsed);
  messagesSent.add(res.status === 200 || res.status === 201 ? 1 : 0);
  sendErrors.add(res.status >= 400 ? 1 : 0);

  check(res, {
    'message sent (200/201)': (r) => r.status === 200 || r.status === 201,
    'has message id': (r) => {
      try { return !!JSON.parse(r.body).data?.id; } catch (e) { return false; }
    },
  });

  if (res.status >= 500) {
    console.warn(`VU${__VU} single: ${res.status} ${elapsed}ms`);
  }

  sleep(0.1 + Math.random() * 0.2);
}

export function sendToDistributedConversations(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  // Each VU consistently targets the same conversation (index-based)
  const convIndex = (__VU - 1) % data.extraConvIds.length;
  const convId = data.extraConvIds[convIndex];

  const payload = JSON.stringify({
    conversation_id: convId,
    content: `Distributed stress msg VU${__VU} conv${convIndex} at ${Date.now()}`,
    type: 'TEXT',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    timeout: '10s',
  };

  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/api/v1/messages/`,
    payload,
    params
  );
  const elapsed = Date.now() - start;

  distributedLatency.add(elapsed);
  messagesSent.add(res.status === 200 || res.status === 201 ? 1 : 0);
  sendErrors.add(res.status >= 400 ? 1 : 0);

  check(res, {
    'message sent (200/201)': (r) => r.status === 200 || r.status === 201,
  });

  if (res.status >= 500) {
    console.warn(`VU${__VU} distributed conv${convIndex}: ${res.status} ${elapsed}ms`);
  }

  sleep(0.1 + Math.random() * 0.2);
}

export function teardown() {
  console.log('\n📊 Message Send Test Complete');
  console.log('   single_conv_send_ms vs distributed_send_ms:');
  console.log('   If distributed is ~10x faster, advisory lock design is correct.');
  console.log('   If similar, check that extra conversations have proper members.');
}
