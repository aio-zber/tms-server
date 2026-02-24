/**
 * Test D: File Listing (FILE-heavy conversation fetch)
 * =====================================================
 * Stress-tests two bottlenecks:
 *   1. Debug query (same as media_messages.js) — doubles DB load
 *   2. Signed URL regeneration — HMAC per file, 100 files = 100 HMACs per request
 *
 * 30 VUs continuously fetch a FILE-heavy conversation for 90 seconds.
 *
 * Run:
 *   k6 run -e CONV_ID=<group_conv_uuid> -e BASE_URL=http://localhost:8000 stress/backend/file_listing.js
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

const fileListLatency = new Trend('file_list_ms', true);
const filePayloadSize = new Trend('file_payload_bytes');
const fileErrors = new Rate('file_errors');
const throughput = new Counter('file_fetches_total');

export const options = {
  scenarios: {
    // Sustained file listing load
    file_listing: {
      executor: 'constant-vus',
      vus: 30,
      duration: '90s',
      exec: 'listFiles',
    },

    // Ramped version to find breaking point
    file_listing_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: 15 },
        { duration: '30s', target: 30 },
        { duration: '30s', target: 60 },
        { duration: '15s', target: 0 },
      ],
      startTime: '100s',  // After sustained test
      exec: 'listFiles',
      gracefulRampDown: '5s',
    },
  },

  thresholds: {
    file_list_ms: [
      { threshold: 'p(95)<5000', abortOnFail: false },
      { threshold: 'p(99)<10000', abortOnFail: false },
    ],
    file_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

export function setup() {
  console.log('\n📁 File Listing Stress Test');
  console.log(`   Conversation: ${CONV_ID} (100 FILE messages)`);
  console.log(`   30 VUs sustained for 90s → ~1,800-5,400 requests`);
  console.log(`   Each request: debug query + 100 HMAC signatures\n`);
  return { convId: CONV_ID };
}

export function listFiles(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];

  const params = {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '15s',
  };

  const start = Date.now();
  const res = http.get(
    `${BASE_URL}/api/v1/messages/conversations/${data.convId}/messages?limit=50`,
    params
  );
  const elapsed = Date.now() - start;

  fileListLatency.add(elapsed);
  filePayloadSize.add(res.body ? res.body.length : 0);
  throughput.add(1);

  const ok = check(res, {
    'listing 200': (r) => r.status === 200,
    'has file messages': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.data) && body.data.some(m => m.type === 'FILE');
      } catch (e) {
        return false;
      }
    },
    'under 5s': (r) => r.timings.duration < 5000,
  });

  fileErrors.add(!ok ? 1 : 0);

  if (!ok || res.status >= 500) {
    console.warn(`VU${__VU}: ${res.status} ${elapsed}ms | ${res.body?.substring(0, 100)}`);
  }

  // Analyze file metadata occasionally
  if (__VU === 1 && Math.random() < 0.03) {
    try {
      const body = JSON.parse(res.body);
      const msgs = Array.isArray(body.data) ? body.data : [];
      const fileMsgs = msgs.filter(m => m.type === 'FILE');
      const withOssKey = fileMsgs.filter(m => m.metadata?.ossKey).length;
      console.log(
        `  📊 ${fileMsgs.length} FILE msgs, ${withOssKey} with ossKey, ` +
        `${(res.body.length / 1024).toFixed(1)}KB, ${elapsed}ms`
      );
    } catch (e) { /* ignore */ }
  }

  // Realistic interval between file listing requests
  sleep(1 + Math.random() * 2);
}

export function teardown() {
  console.log('\n📊 File Listing Test Complete');
  console.log('   file_list_ms: Time per file-listing fetch');
  console.log('   file_payload_bytes: Response size (file metadata)');
  console.log('   file_fetches_total: Total requests served');
  console.log('\n   Bottlenecks:');
  console.log('   1. Debug query (message_repo.py:164) — 2x DB cost per request');
  console.log('   2. HMAC signing per ossKey — O(n) CPU per page');
}
