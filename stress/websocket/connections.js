#!/usr/bin/env node
/**
 * WebSocket Stress Test (Socket.IO)
 * ====================================
 * Requirements:
 *   2. WS roundtrip < 100ms  — HTTP send → WS new_message receive delta
 *   5. Concurrent users      — ramp 0 → 500 → 1000 → 2000 → 3000 connections
 *
 * k6 doesn't support Socket.IO EIO=4 protocol, so this uses socket.io-client.
 *
 * Ramp stages:
 *   0 → 500   ramp, 30s hold
 *   500 → 1000 ramp, 30s hold
 *   1000 → 2000 ramp, 30s hold
 *   2000 → 3000 ramp, 30s hold → disconnect all
 *
 * IMPORTANT: Run with elevated file descriptors first:
 *   ulimit -n 65535
 *   node --max-old-space-size=4096 stress/websocket/connections.js
 *
 * Environment:
 *   BASE_URL=https://tms-chat-staging.hotelsogo-ai.com
 *   MAX_CONNECTIONS=3000   (default)
 *   VERBOSE=1              (log every failed connection)
 */

'use strict';

const { io }    = require('socket.io-client');
const http_mod  = require('http');
const https_mod = require('https');
const fs        = require('fs');
const path      = require('path');

// ─── Config ───────────────────────────────────────────────────────────────────

const BASE_URL         = process.env.BASE_URL         || 'https://tms-chat-staging.hotelsogo-ai.com';
const MAX_CONNECTIONS  = parseInt(process.env.MAX_CONNECTIONS || '3000', 10);
const VERBOSE          = process.env.VERBOSE === '1';
const DATA_DIR         = path.join(__dirname, '..', 'data');
const RESULTS_DIR      = path.join(__dirname, '..', 'results');

fs.mkdirSync(RESULTS_DIR, { recursive: true });

// ─── Load test data ───────────────────────────────────────────────────────────

let tokens   = [];
let convData = {};

try {
  tokens = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'tokens_array.json'), 'utf8'));
  console.log(`✅ Loaded ${tokens.length} tokens`);
} catch (e) {
  console.error('❌ tokens_array.json not found. Run generate_tokens.py first.');
  process.exit(1);
}

try {
  convData = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'conversation_ids.json'), 'utf8'));
} catch (e) {
  console.error('❌ conversation_ids.json not found. Run seed_data.py first.');
  process.exit(1);
}

// Use extra conversations for roundtrip probes to avoid group conversation noise
const probeConvIds = (convData.extra_conversation_ids && convData.extra_conversation_ids.length > 0)
  ? convData.extra_conversation_ids
  : [convData.group_conversation_id];

// ─── Metrics ──────────────────────────────────────────────────────────────────

const metrics = {
  connectTimes:        [],   // ms from io() call to 'connect' event
  roundtripLatencies:  [],   // ms from HTTP POST → WS new_message received
  roundtripSamples:    0,
  disconnects:         0,
  errors:              0,
  timeouts:            0,
  successful:          0,
  failed:              0,
  errorsByStage:       {},
  events:              [],
};

function recordEvent(type, data = {}) {
  metrics.events.push({ ts: Date.now(), type, ...data });
}

function percentile(arr, p) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  return sorted[Math.min(Math.floor(sorted.length * p / 100), sorted.length - 1)];
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ─── HTTP POST helper (roundtrip probe) ───────────────────────────────────────
// Uses Node's native http/https to avoid socket.io-client intercepting it.

function postMessage(token, convId, content) {
  return new Promise((resolve, reject) => {
    const body    = JSON.stringify({ conversation_id: convId, content, type: 'TEXT' });
    const isHttps = BASE_URL.startsWith('https');
    const mod     = isHttps ? https_mod : http_mod;
    const url     = new URL(`${BASE_URL}/api/v1/messages/`);

    const req = mod.request({
      hostname: url.hostname,
      port:     url.port || (isHttps ? 443 : 80),
      path:     url.pathname,
      method:   'POST',
      headers: {
        'Content-Type':   'application/json',
        'Authorization':  `Bearer ${token}`,
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      res.resume();  // drain body
      resolve(res.statusCode);
    });

    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('HTTP timeout')); });
    req.write(body);
    req.end();
  });
}

// ─── Connection factory ───────────────────────────────────────────────────────

function createConnection(index) {
  return new Promise((resolve, reject) => {
    const token   = tokens[index % tokens.length];
    const convId  = probeConvIds[index % probeConvIds.length];
    const start   = Date.now();

    const socket = io(BASE_URL, {
      auth:         { token },
      transports:   ['websocket'],
      reconnection: false,
      timeout:      15000,
      path:         '/socket.io/',
    });

    const timer = setTimeout(() => {
      socket.disconnect();
      metrics.timeouts++;
      metrics.failed++;
      if (VERBOSE) console.warn(`  ⏱  Connection ${index} timed out after 15s`);
      reject(new Error(`Connection ${index} timed out`));
    }, 15000);

    socket.on('connect', () => {
      clearTimeout(timer);
      metrics.connectTimes.push(Date.now() - start);
      metrics.successful++;
      recordEvent('connect', { index, connectTime: Date.now() - start });
    });

    socket.on('connect_error', (err) => {
      clearTimeout(timer);
      metrics.errors++;
      metrics.failed++;
      recordEvent('connect_error', { index, error: err.message });
      reject(err);
    });

    socket.on('disconnect', (reason) => {
      metrics.disconnects++;
      recordEvent('disconnect', { index, reason });
    });

    // ── Roundtrip measurement (Requirement 2) ──────────────────────────────
    // After rooms_joined we know the socket is fully registered.
    // We register the new_message listener BEFORE posting to avoid race condition.
    let probeDone = false;
    socket.once('rooms_joined', async () => {
      if (probeDone) { resolve(socket); return; }
      probeDone = true;

      // Unique probe content so cross-socket messages don't trigger the wrong timer
      const probeContent = `_rt_probe_${index}_${Date.now()}`;

      // Listen first, then post — eliminates sub-ms race condition
      const probeStart = Date.now();

      const onNewMessage = (msg) => {
        const content = msg?.content || msg?.data?.content || '';
        if (content === probeContent) {
          const delta = Date.now() - probeStart;
          metrics.roundtripLatencies.push(delta);
          metrics.roundtripSamples++;
          recordEvent('roundtrip', { index, delta_ms: delta });
          socket.off('new_message', onNewMessage);
        }
      };
      socket.on('new_message', onNewMessage);

      try {
        const status = await postMessage(token, convId, probeContent);
        if (status !== 200 && status !== 201 && VERBOSE) {
          console.warn(`  Roundtrip HTTP ${status} for conn ${index}`);
        }
      } catch (err) {
        if (VERBOSE) console.warn(`  Roundtrip HTTP error for conn ${index}: ${err.message}`);
        socket.off('new_message', onNewMessage);
      }

      // Resolve regardless of roundtrip outcome — connection itself is valid
      setTimeout(() => resolve(socket), 200);
    });

    // Fall back: resolve after 5s if rooms_joined never fires
    setTimeout(() => {
      if (!probeDone) {
        probeDone = true;
        resolve(socket);
      }
    }, 5000);
  });
}

// ─── Ramp + hold helpers ──────────────────────────────────────────────────────

async function rampStage(label, fromIdx, toIdx, existingSockets, batchSize, batchIntervalMs) {
  if (!metrics.errorsByStage[label]) metrics.errorsByStage[label] = 0;
  console.log(`\n📈 Ramp [${label}]: ${fromIdx} → ${toIdx} connections`);

  const newSockets = [];

  for (let i = fromIdx; i < toIdx; i += batchSize) {
    const batchEnd  = Math.min(i + batchSize, toIdx);
    const batch     = [];

    for (let j = i; j < batchEnd; j++) {
      batch.push(
        createConnection(j)
          .then(sock => newSockets.push(sock))
          .catch(() => { metrics.errorsByStage[label]++; })
      );
    }

    await Promise.allSettled(batch);

    const total = existingSockets.length + newSockets.length;
    process.stdout.write(
      `\r   connected=${total} failed=${metrics.failed} ` +
      `rt_samples=${metrics.roundtripSamples} ` +
      `rt_p50=${percentile(metrics.roundtripLatencies, 50)}ms`
    );

    if (i + batchSize < toIdx) await sleep(batchIntervalMs);
  }

  const allSockets = existingSockets.concat(newSockets);
  const active     = allSockets.filter(s => s && s.connected).length;
  const errorRate  = metrics.failed / Math.max(1, metrics.successful + metrics.failed);

  console.log(`\n   ✅ Ramp [${label}] complete`);
  console.log(`      Active: ${active}  Failed: ${metrics.failed}  Error rate: ${(errorRate * 100).toFixed(1)}%`);
  console.log(`      Roundtrip p50=${percentile(metrics.roundtripLatencies, 50)}ms  p95=${percentile(metrics.roundtripLatencies, 95)}ms  samples=${metrics.roundtripSamples}`);

  return allSockets;
}

async function holdStage(label, sockets, durationMs) {
  const initial = sockets.filter(s => s && s.connected).length;
  console.log(`\n⏸️  Hold [${label}]: ${initial} connections for ${durationMs / 1000}s`);

  const start         = Date.now();
  const checkInterval = setInterval(() => {
    const active    = sockets.filter(s => s && s.connected).length;
    const dropped   = initial - active;
    const elapsed   = ((Date.now() - start) / 1000).toFixed(0);
    const errRate   = (metrics.failed / Math.max(1, metrics.successful + metrics.failed) * 100).toFixed(1);
    process.stdout.write(
      `\r   [${elapsed}s] active=${active}/${initial} dropped=${dropped} error_rate=${errRate}%`
    );
  }, 5000);

  await sleep(durationMs);
  clearInterval(checkInterval);

  const stillActive = sockets.filter(s => s && s.connected).length;
  const dropped     = initial - stillActive;
  console.log(`\n   ✅ Hold [${label}] complete: ${stillActive}/${initial} connected, ${dropped} dropped`);
  recordEvent('hold_complete', { label, still_connected: stillActive, dropped });

  return sockets;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  // OS FD check
  try {
    const { execSync } = require('child_process');
    const fdLimit = parseInt(execSync('ulimit -n', { encoding: 'utf8' }).trim(), 10);
    if (fdLimit < 10000) {
      console.warn(`⚠️  ulimit -n = ${fdLimit}. For ${MAX_CONNECTIONS} connections, run: ulimit -n 65535`);
    } else {
      console.log(`✅ File descriptor limit: ${fdLimit}`);
    }
  } catch (e) { /* ignore on non-unix */ }

  console.log('\n🚀 WebSocket Stress Test (Requirements 2 + 5)');
  console.log(`   Server:      ${BASE_URL}`);
  console.log(`   Target:      ${MAX_CONNECTIONS} connections`);
  console.log(`   Roundtrip:   HTTP send → WS new_message (target p95 < 100ms)`);
  console.log(`   Probe convs: ${probeConvIds.length}\n`);

  const totalStart = Date.now();
  let sockets      = [];

  try {
    // Stage 1: 0 → 500
    sockets = await rampStage('ramp_0_500',   0,    500,                 sockets, 10, 100);
    sockets = await holdStage('hold_500',     sockets, 30_000);

    // Stage 2: 500 → 1000
    sockets = await rampStage('ramp_500_1k',  500,  1000,                sockets, 10, 100);
    sockets = await holdStage('hold_1k',      sockets, 30_000);

    // Stage 3: 1000 → 2000
    sockets = await rampStage('ramp_1k_2k',   1000, 2000,                sockets, 20, 100);
    sockets = await holdStage('hold_2k',      sockets, 30_000);

    // Stage 4: 2000 → target (default 3000)
    sockets = await rampStage('ramp_2k_peak', 2000, MAX_CONNECTIONS,     sockets, 20, 100);
    sockets = await holdStage('hold_peak',    sockets, 30_000);
  } catch (err) {
    console.error('❌ Test error:', err.message);
  }

  // Disconnect all
  const activeCount = sockets.filter(s => s && s.connected).length;
  console.log(`\n🔌 Disconnecting ${activeCount} connections...`);
  sockets.forEach(s => { if (s && s.connected) s.disconnect(); });
  await sleep(5000);

  // ─── Results ────────────────────────────────────────────────────────────────

  const rt95      = percentile(metrics.roundtripLatencies, 95);
  const errorRate = metrics.failed / Math.max(1, MAX_CONNECTIONS);

  const results = {
    timestamp:          new Date().toISOString(),
    server:             BASE_URL,
    total_duration_ms:  Date.now() - totalStart,
    target_connections: MAX_CONNECTIONS,

    connections: {
      attempted:  MAX_CONNECTIONS,
      successful: metrics.successful,
      failed:     metrics.failed,
      timeouts:   metrics.timeouts,
      error_rate: parseFloat(errorRate.toFixed(4)),
    },

    connect_time_ms: {
      p50: percentile(metrics.connectTimes, 50),
      p95: percentile(metrics.connectTimes, 95),
      p99: percentile(metrics.connectTimes, 99),
      max: Math.max(0, ...metrics.connectTimes),
    },

    // Requirement 2: WS roundtrip latency
    roundtrip_ms: {
      samples: metrics.roundtripSamples,
      p50:     percentile(metrics.roundtripLatencies, 50),
      p95:     rt95,
      p99:     percentile(metrics.roundtripLatencies, 99),
      max:     Math.max(0, ...metrics.roundtripLatencies),
      pass_requirement_2: rt95 < 100,
    },

    // Requirement 5: error rate at peak
    errors_by_stage:       metrics.errorsByStage,
    pass_requirement_5:    errorRate < 0.05,
  };

  console.log('\n' + '═'.repeat(60));
  console.log('📊 WEBSOCKET STRESS TEST RESULTS');
  console.log('═'.repeat(60));
  console.log(JSON.stringify(results, null, 2));

  // Requirement verdicts
  console.log('\n🏁 VERDICT');
  console.log('─'.repeat(40));

  console.log(`Requirement 2 — WS Roundtrip < 100ms:`);
  if (metrics.roundtripSamples === 0) {
    console.log('  ⚠️  NO SAMPLES — rooms_joined event may not be firing. Check server socket events.');
  } else if (rt95 < 100) {
    console.log(`  ✅ PASS: p95 = ${rt95}ms (${metrics.roundtripSamples} samples)`);
  } else {
    console.log(`  ❌ FAIL: p95 = ${rt95}ms (target < 100ms)`);
  }

  console.log(`\nRequirement 5 — ${MAX_CONNECTIONS} concurrent WebSocket connections:`);
  console.log(`  Successful: ${results.connections.successful}/${MAX_CONNECTIONS}`);
  console.log(`  Error rate: ${(errorRate * 100).toFixed(1)}%`);
  if (errorRate < 0.05) {
    console.log(`  ✅ PASS: error rate < 5%`);
  } else if (errorRate < 0.10) {
    console.log(`  ⚠️  WARN: error rate ${(errorRate * 100).toFixed(1)}% (5-10%)`);
  } else {
    console.log(`  ❌ FAIL: error rate ${(errorRate * 100).toFixed(1)}% (> 10%)`);
  }

  // Write results file
  const resultsFile = path.join(RESULTS_DIR, `websocket_${Date.now()}.json`);
  fs.writeFileSync(resultsFile, JSON.stringify({ results, events: metrics.events }, null, 2));
  console.log(`\n💾 Results: ${resultsFile}`);
}

main()
  .catch(console.error)
  .finally(() => setTimeout(() => process.exit(0), 3000));
