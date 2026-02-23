/**
 * Test A: Poll Concurrent Voting
 * ===============================
 * Stress-tests the with_for_update() row-level lock in poll_service.py:194.
 *
 * Expected breakdown points:
 *  - ≤15 VUs  → Fine     (~100ms p95)
 *  - 16-30 VUs → Slows down (lock queue builds, 1-3s p95)
 *  - 31+ VUs   → Crashes (pool exhausted 503s)
 *
 * Run:
 *   k6 run -e POLL_ID=<uuid> -e BASE_URL=http://localhost:8000 stress/backend/poll_vote.js
 *
 * Monitor in parallel:
 *   psql -f stress/monitoring/pg_queries.sql
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

// ─── Configuration ─────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const POLL_ID = __ENV.POLL_ID || (() => {
  // Fallback: read from data file via env
  console.warn('⚠️  POLL_ID not set. Pass -e POLL_ID=<uuid>');
  return 'unknown';
})();

// Load tokens from file
const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});

// Load poll option IDs
const pollOptions = new SharedArray('poll_options', function () {
  return JSON.parse(open('../data/poll_option_ids.json'));
});

// ─── Custom Metrics ─────────────────────────────────────────────────────────────

const voteErrors = new Rate('vote_errors');
const voteLatency = new Trend('vote_latency_ms', true);
const lockWaitTime = new Trend('lock_wait_ms', true);
const poolExhausted = new Counter('pool_exhausted_503');
const lockTimeouts = new Counter('lock_timeout_errors');

// ─── Scenarios ─────────────────────────────────────────────────────────────────

export const options = {
  scenarios: {
    // Scenario 1: Ramp test — gradually increase VUs
    ramp_voting: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 10 },  // Warm up
        { duration: '20s', target: 30 },  // Hit pool limit
        { duration: '30s', target: 50 },  // Exceed pool
        { duration: '30s', target: 100 }, // Full stress
        { duration: '20s', target: 0 },   // Cool down
      ],
      gracefulRampDown: '10s',
      exec: 'voteOnPoll',
    },

    // Scenario 2: Spike — 500 simultaneous votes in 5s burst
    // Uncomment to run spike test separately
    // spike_voting: {
    //   executor: 'constant-arrival-rate',
    //   rate: 100,         // 100 votes per second
    //   timeUnit: '1s',
    //   duration: '5s',    // 5s burst = 500 votes
    //   preAllocatedVUs: 200,
    //   maxVUs: 500,
    //   exec: 'voteOnPoll',
    //   startTime: '120s', // Run after ramp test completes
    // },
  },

  thresholds: {
    // Ramp test thresholds
    'vote_latency_ms{scenario:ramp_voting}': [
      { threshold: 'p(95)<2000', abortOnFail: false },
      { threshold: 'p(99)<5000', abortOnFail: false },
    ],
    // Overall error rate must stay below 5%
    vote_errors: [{ threshold: 'rate<0.05', abortOnFail: false }],
    // HTTP errors
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

// ─── Setup ─────────────────────────────────────────────────────────────────────

export function setup() {
  console.log(`\n🗳️  Poll Voting Stress Test`);
  console.log(`   Poll ID: ${POLL_ID}`);
  console.log(`   Options: ${pollOptions.length}`);
  console.log(`   Users: ${tokens.length}`);
  console.log(`   Target: 100 VUs (pool limit: 30 connections)\n`);

  // Verify the poll exists
  const token = tokens[0];
  const res = http.get(`${BASE_URL}/api/v1/polls/${POLL_ID}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status !== 200) {
    console.error(`❌ Poll ${POLL_ID} not accessible: ${res.status} ${res.body}`);
  } else {
    console.log(`✅ Poll verified: ${res.status}`);
  }

  return { pollId: POLL_ID, options: pollOptions };
}

// ─── Main VU Function ───────────────────────────────────────────────────────────

export function voteOnPoll(data) {
  const vuIndex = __VU % tokens.length;
  const token = tokens[vuIndex];
  const optionId = data.options[Math.floor(Math.random() * data.options.length)];

  const payload = JSON.stringify({ option_ids: [optionId] });
  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    timeout: '10s',
    tags: { scenario: 'ramp_voting' },
  };

  const startTime = Date.now();
  const res = http.post(`${BASE_URL}/api/v1/polls/${data.pollId}/vote`, payload, params);
  const elapsed = Date.now() - startTime;

  voteLatency.add(elapsed);

  // Track specific error types
  if (res.status === 503) {
    poolExhausted.add(1);
    voteErrors.add(1);
    console.warn(`⚠️  503 at VU${__VU}: DB pool exhausted`);
  } else if (res.status === 429) {
    // Rate limited — expected at very high VUs, not a bottleneck issue
    voteErrors.add(0);
  } else if (res.status === 409) {
    // Already voted — expected (each user can only vote once per run)
    voteErrors.add(0);
  } else if (res.status === 500) {
    lockTimeouts.add(1);
    voteErrors.add(1);
    console.warn(`⚠️  500 at VU${__VU}: Server error (possible lock timeout)`);
  } else {
    voteErrors.add(res.status >= 400 ? 1 : 0);
  }

  const ok = check(res, {
    'vote accepted (200 or 201)': (r) => r.status === 200 || r.status === 201,
    'response time < 5s': (r) => r.timings.duration < 5000,
    'no 503 pool exhaustion': (r) => r.status !== 503,
  });

  if (!ok && res.status !== 409 && res.status !== 429) {
    console.log(`VU${__VU} | status=${res.status} | ${elapsed}ms | body=${res.body?.substring(0, 200)}`);
  }

  // Brief sleep to simulate realistic user behavior
  sleep(0.1 + Math.random() * 0.5);
}

// ─── Teardown ─────────────────────────────────────────────────────────────────

export function teardown(data) {
  console.log('\n📊 Poll Vote Test Complete');
  console.log('   Check stress/results/poll_vote_*.json for detailed metrics');
  console.log(`   To reset poll votes for next run:`);
  console.log(`   psql -c "DELETE FROM poll_votes WHERE poll_id='${POLL_ID}'"`);
}
