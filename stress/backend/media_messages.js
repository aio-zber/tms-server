/**
 * Test C: Media Messages (IMAGE-heavy conversation fetch)
 * ========================================================
 * Stress-tests the debug query bottleneck in message_repo.py:164-182.
 * Every message page fetch triggers TWO queries:
 *   1. Paginated query (correct, limited)
 *   2. Full-table scan: SELECT * FROM messages WHERE conv_id=? (NO LIMIT)
 *
 * With 100+ image messages, query #2 loads ALL rows every time.
 *
 * Scenario 1: 50 VUs simultaneously open IMAGE-heavy conversation
 * Scenario 2: 20 VUs paginate 5 pages each (simulate scroll-to-top)
 *
 * Run:
 *   k6 run -e CONV_ID=<group_conv_uuid> -e BASE_URL=http://localhost:8000 stress/backend/media_messages.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL = __ENV.BASE_URL || 'https://tms-chat-staging.hotelsogo-ai.com';
const CONV_ID = __ENV.CONV_ID || (() => {
  try {
    return JSON.parse(open('../data/conversation_ids.json')).group_conversation_id;
  } catch (e) {
    return 'unknown';
  }
})();

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});

// ─── Custom Metrics ─────────────────────────────────────────────────────────────

const fetchLatency = new Trend('media_fetch_ms', true);
const pageFetchLatency = new Trend('page_fetch_ms', true);
const payloadSize = new Trend('media_payload_bytes');
const fetchErrors = new Rate('media_fetch_errors');
const debugQueryOverhead = new Trend('debug_query_overhead_ms');

export const options = {
  scenarios: {
    // Scenario 1: Concurrent conversation open
    open_conversation: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
      exec: 'openConversation',
    },

    // Scenario 2: Scroll pagination (load older messages)
    paginate_messages: {
      executor: 'constant-vus',
      vus: 20,
      duration: '90s',
      startTime: '70s',  // After scenario 1
      exec: 'paginateMessages',
    },
  },

  thresholds: {
    // With debug query: expect slow
    'media_fetch_ms': [
      { threshold: 'p(95)<5000', abortOnFail: false },
      { threshold: 'p(99)<10000', abortOnFail: false },
    ],
    // Page fetch during scroll
    'page_fetch_ms': [
      { threshold: 'p(95)<3000', abortOnFail: false },
    ],
    media_fetch_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

export function setup() {
  console.log('\n🖼️  Media Messages Stress Test');
  console.log(`   Conversation: ${CONV_ID} (100 IMAGE + 100 FILE messages)`);
  console.log(`   Scenario 1: 50 VUs × 60s concurrent open`);
  console.log(`   Scenario 2: 20 VUs × 5 page scrolls`);
  console.log(`\n   ⚠️  DEBUG QUERY: Each fetch runs unbounded SELECT *`);
  console.log(`       Expect 2x DB load vs. what it should be\n`);
  return { convId: CONV_ID };
}

// ─── Scenario 1: Open conversation ────────────────────────────────────────────

export function openConversation(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  const params = {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '20s',
    tags: { scenario: 'open_conversation' },
  };

  const start = Date.now();
  const res = http.get(
    `${BASE_URL}/api/v1/messages/conversations/${data.convId}/messages?limit=50`,
    params
  );
  const elapsed = Date.now() - start;

  fetchLatency.add(elapsed);
  payloadSize.add(res.body ? res.body.length : 0);

  const ok = check(res, {
    'conversation opened (200)': (r) => r.status === 200,
    'has media messages': (r) => {
      try {
        const body = JSON.parse(r.body);
        const msgs = Array.isArray(body.data) ? body.data : [];
        // First page shows most-recent messages (FILE seeded last, IMAGE before that)
        return msgs.some(m => m.type === 'IMAGE' || m.type === 'FILE');
      } catch (e) {
        return false;
      }
    },
    'under 5s': (r) => r.timings.duration < 5000,
  });

  fetchErrors.add(!ok ? 1 : 0);

  if (res.status !== 200 && Math.random() < 0.3) {
    console.warn(`VU${__VU} open: ${res.status} ${elapsed}ms`);
  }

  // Log payload stats occasionally
  if (__VU <= 2 && Math.random() < 0.05) {
    try {
      const body = JSON.parse(res.body);
      const msgs = Array.isArray(body.data) ? body.data : [];
      const imageMsgs = msgs.filter(m => m.type === 'IMAGE').length;
      console.log(`  📊 VU${__VU}: ${msgs.length} msgs (${imageMsgs} images), ${(res.body.length / 1024).toFixed(1)}KB, ${elapsed}ms`);
    } catch (e) { /* ignore */ }
  }

  sleep(1 + Math.random() * 2);
}

// ─── Scenario 2: Paginate messages (scroll to top) ────────────────────────────

export function paginateMessages(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  const params = {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '20s',
    tags: { scenario: 'paginate_messages' },
  };

  let cursor = null;
  let pageCount = 0;
  const MAX_PAGES = 5;

  while (pageCount < MAX_PAGES) {
    const url = cursor
      ? `${BASE_URL}/api/v1/messages/conversations/${data.convId}/messages?limit=50&cursor=${cursor}`
      : `${BASE_URL}/api/v1/messages/conversations/${data.convId}/messages?limit=50`;

    const start = Date.now();
    const res = http.get(url, params);
    const elapsed = Date.now() - start;

    pageFetchLatency.add(elapsed);

    const ok = check(res, {
      'page 200': (r) => r.status === 200,
      'page under 3s': (r) => r.timings.duration < 3000,
    });

    if (!ok) {
      console.warn(`VU${__VU} page ${pageCount}: ${res.status} ${elapsed}ms`);
      break;
    }

    try {
      const body = JSON.parse(res.body);
      cursor = body.pagination?.next_cursor;
      const hasMore = body.pagination?.has_more;

      if (__VU === 1) {
        console.log(`  📜 Page ${pageCount + 1}: cursor=${cursor?.substring(0, 20)}..., has_more=${hasMore}, ${elapsed}ms`);
      }

      if (!hasMore) break;
    } catch (e) {
      break;
    }

    pageCount++;
    sleep(0.5 + Math.random() * 0.5);
  }

  sleep(2 + Math.random() * 3);
}

export function teardown() {
  console.log('\n📊 Media Messages Test Complete');
  console.log('   media_fetch_ms: Conversation open latency');
  console.log('   page_fetch_ms: Pagination latency');
  console.log('   media_payload_bytes: Response size per fetch');
  console.log('\n   Root cause: debug query in message_repo.py:164-182');
  console.log('   Fix: Remove the debug SELECT * block (saves 50-80% DB time)');
}
