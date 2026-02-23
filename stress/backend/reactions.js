/**
 * Test B: Reaction Stress Test
 * =============================
 * Two phases:
 *   Phase 1 (write): 100 VUs each add 5 reactions = 500 total across 100 messages
 *   Phase 2 (read):  50 VUs fetch message pages with heavy reaction load
 *
 * Bottleneck: selectinload(Message.reactions) loads ALL reaction rows per page.
 * 50 messages × 100 reactions = 5,000 rows per page request.
 *
 * Run:
 *   k6 run -e CONV_ID=<group_conv_uuid> -e BASE_URL=http://localhost:8000 stress/backend/reactions.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const CONV_ID = __ENV.CONV_ID || (() => {
  try {
    const data = JSON.parse(open('../data/conversation_ids.json'));
    return data.group_conversation_id;
  } catch (e) {
    console.error('❌ Pass -e CONV_ID=<uuid> or run seed_data.py first');
    return 'unknown';
  }
})();

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});

const messageIds = new SharedArray('messages', function () {
  const data = JSON.parse(open('../data/message_ids.json'));
  return data.image_message_ids;  // 100 image messages to react to
});

// ─── Custom Metrics ─────────────────────────────────────────────────────────────

const reactionWriteLatency = new Trend('reaction_write_ms', true);
const reactionReadLatency = new Trend('reaction_read_ms', true);
const reactionErrors = new Rate('reaction_errors');
const pageLoadErrors = new Rate('page_load_errors');
const pagePayloadSize = new Trend('page_payload_bytes');

// Common emojis to react with
const EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '😡', '🎉', '🔥', '👀', '💯'];

export const options = {
  scenarios: {
    // Phase 1: Write reactions
    reaction_write: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 50 },   // Ramp to 50
        { duration: '30s', target: 100 },  // Full 100 VUs adding reactions
        { duration: '20s', target: 0 },    // Cool down
      ],
      exec: 'addReaction',
      gracefulRampDown: '5s',
    },

    // Phase 2: Read pages with heavy reaction load
    reaction_read: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
      startTime: '70s',  // Start after write phase
      exec: 'fetchMessagesWithReactions',
    },
  },

  thresholds: {
    'reaction_write_ms': [
      { threshold: 'p(95)<500', abortOnFail: false },
      { threshold: 'p(99)<1000', abortOnFail: false },
    ],
    'reaction_read_ms': [
      { threshold: 'p(95)<3000', abortOnFail: false },
      { threshold: 'p(99)<8000', abortOnFail: false },
    ],
    reaction_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    page_load_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

export function setup() {
  console.log('\n❤️  Reaction Stress Test');
  console.log(`   Conversation: ${CONV_ID}`);
  console.log(`   Message pool: ${messageIds.length} messages`);
  console.log(`   Write phase: 100 VUs × 5 reactions = 500 reactions`);
  console.log(`   Read phase: 50 VUs fetching pages with accumulated reactions\n`);
  return { convId: CONV_ID };
}

// ─── Phase 1: Add reactions ────────────────────────────────────────────────────

export function addReaction(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  // Each VU adds 5 reactions to random messages
  for (let i = 0; i < 5; i++) {
    const msgId = messageIds[Math.floor(Math.random() * messageIds.length)];
    const emoji = EMOJIS[Math.floor(Math.random() * EMOJIS.length)];

    const payload = JSON.stringify({ emoji });
    const params = {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      timeout: '5s',
    };

    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/api/v1/messages/${msgId}/reactions`,
      payload,
      params
    );
    const elapsed = Date.now() - start;

    reactionWriteLatency.add(elapsed);

    const ok = check(res, {
      'reaction added (200/201/409)': (r) => [200, 201, 409].includes(r.status),
      'no 5xx errors': (r) => r.status < 500,
      'under 500ms': (r) => r.timings.duration < 500,
    });

    reactionErrors.add(!ok && res.status >= 500 ? 1 : 0);

    if (res.status >= 500) {
      console.warn(`VU${__VU} reaction ${i}: ${res.status} ${res.body?.substring(0, 100)}`);
    }

    sleep(0.05 + Math.random() * 0.1);
  }

  sleep(0.2);
}

// ─── Phase 2: Fetch message pages with reactions ───────────────────────────────

export function fetchMessagesWithReactions(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  const params = {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '15s',
  };

  // Fetch first page (most recent 50 messages, each with many reactions)
  const start = Date.now();
  const res = http.get(
    `${BASE_URL}/api/v1/conversations/${data.convId}/messages?limit=50`,
    params
  );
  const elapsed = Date.now() - start;

  reactionReadLatency.add(elapsed);
  pagePayloadSize.add(res.body ? res.body.length : 0);

  const ok = check(res, {
    'page fetch 200': (r) => r.status === 200,
    'has messages': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && Array.isArray(body.data.messages);
      } catch (e) {
        return false;
      }
    },
    'page load < 3s': (r) => r.timings.duration < 3000,
  });

  pageLoadErrors.add(!ok ? 1 : 0);

  if (res.status !== 200) {
    console.warn(`VU${__VU} page fetch: ${res.status} ${res.body?.substring(0, 200)}`);
  } else {
    try {
      const body = JSON.parse(res.body);
      const msgCount = body.data?.messages?.length || 0;
      const totalReactions = body.data?.messages?.reduce(
        (acc, m) => acc + (m.reactions?.length || 0), 0
      ) || 0;
      if (__VU === 1 && Math.random() < 0.1) {
        console.log(`  📊 Page: ${msgCount} msgs, ${totalReactions} reactions, ${res.body.length} bytes, ${elapsed}ms`);
      }
    } catch (e) { /* ignore parse errors */ }
  }

  sleep(0.5 + Math.random() * 1.0);
}

export function teardown(data) {
  console.log('\n📊 Reaction Test Complete');
  console.log('   Check reaction_write_ms and reaction_read_ms metrics');
  console.log('   page_payload_bytes shows response size growth with reactions');
}
