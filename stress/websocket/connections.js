#!/usr/bin/env node
/**
 * WebSocket Stress Test (Socket.IO)
 * ===================================
 * k6 doesn't support Socket.IO EIO=4 protocol, so this uses socket.io-client.
 *
 * Scenarios:
 *  1. Ramp: 0 → 200 connections at 10 connections per 100ms
 *  2. Hold: 200 connections open for 30s
 *  3. Measure disconnect / cleanup time
 *
 * Expected bottleneck at 200 simultaneous connects:
 *  Each connect triggers `SELECT conversation_ids FROM conversation_members WHERE user_id=?`
 *  200 queries hitting the 30-connection pool simultaneously → queueing
 *
 * Install dependencies first:
 *   npm install socket.io-client
 *
 * Run:
 *   node stress/websocket/connections.js
 */

const { io } = require('socket.io-client');
const fs = require('fs');
const path = require('path');

// ─── Config ─────────────────────────────────────────────────────────────────────

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const DATA_DIR = path.join(__dirname, '..', 'data');
const RESULTS_DIR = path.join(__dirname, '..', 'results');

// Ensure results directory exists
fs.mkdirSync(RESULTS_DIR, { recursive: true });

// Load tokens
let tokens = [];
try {
  tokens = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'tokens_array.json'), 'utf8'));
  console.log(`✅ Loaded ${tokens.length} tokens`);
} catch (e) {
  console.error('❌ tokens_array.json not found. Run generate_tokens.py first.');
  process.exit(1);
}

// ─── Metrics ─────────────────────────────────────────────────────────────────────

const metrics = {
  connectTimes: [],
  disconnects: 0,
  errors: 0,
  timeouts: 0,
  successful: 0,
  failed: 0,
  events: [],
};

function recordEvent(type, data = {}) {
  metrics.events.push({ ts: Date.now(), type, ...data });
}

function percentile(arr, p) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.floor(sorted.length * (p / 100));
  return sorted[Math.min(idx, sorted.length - 1)];
}

// ─── Connection Factory ─────────────────────────────────────────────────────────

function createConnection(index) {
  return new Promise((resolve, reject) => {
    const token = tokens[index % tokens.length];
    const startTime = Date.now();

    const socket = io(BASE_URL, {
      auth: { token },
      transports: ['websocket'],  // Force WS (skip polling)
      reconnection: false,         // No auto-reconnect during stress test
      timeout: 10000,              // 10s connection timeout
      path: '/socket.io/',
    });

    const timer = setTimeout(() => {
      socket.disconnect();
      metrics.timeouts++;
      metrics.failed++;
      reject(new Error(`Connection ${index} timed out after 10s`));
    }, 10000);

    socket.on('connect', () => {
      clearTimeout(timer);
      const connectTime = Date.now() - startTime;
      metrics.connectTimes.push(connectTime);
      metrics.successful++;
      recordEvent('connect', { index, connectTime });
      resolve(socket);
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

    // Track any messages received
    socket.onAny((event, data) => {
      if (event !== 'connect' && event !== 'disconnect') {
        recordEvent('message', { index, event });
      }
    });
  });
}

// ─── Test Scenarios ─────────────────────────────────────────────────────────────

async function scenario1_ramp() {
  console.log('\n📡 Scenario 1: Ramp 0 → 200 connections (10 per 100ms)');
  const sockets = [];
  const MAX_CONNECTIONS = Math.min(200, tokens.length);
  const BATCH_SIZE = 10;
  const BATCH_INTERVAL_MS = 100;

  const rampStart = Date.now();
  recordEvent('ramp_start', { target: MAX_CONNECTIONS });

  for (let i = 0; i < MAX_CONNECTIONS; i += BATCH_SIZE) {
    const batchEnd = Math.min(i + BATCH_SIZE, MAX_CONNECTIONS);
    const batchPromises = [];

    for (let j = i; j < batchEnd; j++) {
      batchPromises.push(
        createConnection(j)
          .then(sock => { sockets.push(sock); })
          .catch(err => {
            if (process.env.VERBOSE) {
              console.warn(`  ⚠️  Connection ${j} failed: ${err.message}`);
            }
          })
      );
    }

    await Promise.allSettled(batchPromises);
    console.log(
      `  Batch ${Math.floor(i / BATCH_SIZE) + 1}: ${sockets.length} connected, ` +
      `${metrics.failed} failed, ${metrics.errors} errors`
    );

    if (i + BATCH_SIZE < MAX_CONNECTIONS) {
      await sleep(BATCH_INTERVAL_MS);
    }
  }

  const rampDuration = Date.now() - rampStart;
  recordEvent('ramp_complete', {
    duration_ms: rampDuration,
    connected: sockets.length,
    failed: metrics.failed,
  });

  console.log(`\n✅ Ramp complete in ${rampDuration}ms`);
  console.log(`   Connected: ${sockets.length}/${MAX_CONNECTIONS}`);
  console.log(`   Failed: ${metrics.failed}`);
  console.log(`   Connect time p50: ${percentile(metrics.connectTimes, 50)}ms`);
  console.log(`   Connect time p95: ${percentile(metrics.connectTimes, 95)}ms`);
  console.log(`   Connect time p99: ${percentile(metrics.connectTimes, 99)}ms`);

  return sockets;
}

async function scenario2_hold(sockets) {
  const HOLD_DURATION_MS = 30000;  // 30 seconds

  console.log(`\n⏸️  Scenario 2: Holding ${sockets.length} connections for ${HOLD_DURATION_MS / 1000}s`);

  const holdStart = Date.now();
  const initialConnected = sockets.length;

  // Send heartbeat messages every 5s to keep connections alive
  const heartbeatInterval = setInterval(() => {
    const active = sockets.filter(s => s && s.connected).length;
    console.log(
      `  Hold: ${active}/${initialConnected} still connected ` +
      `(${Date.now() - holdStart}ms elapsed)`
    );
  }, 5000);

  await sleep(HOLD_DURATION_MS);
  clearInterval(heartbeatInterval);

  const stillConnected = sockets.filter(s => s && s.connected).length;
  const unexpectedDrops = initialConnected - stillConnected - metrics.disconnects;

  recordEvent('hold_complete', {
    duration_ms: HOLD_DURATION_MS,
    still_connected: stillConnected,
    unexpected_drops: unexpectedDrops,
  });

  console.log(`✅ Hold complete`);
  console.log(`   Still connected: ${stillConnected}/${initialConnected}`);
  console.log(`   Unexpected drops during hold: ${Math.max(0, unexpectedDrops)}`);

  return sockets;
}

async function scenario3_disconnect(sockets) {
  console.log(`\n🔌 Scenario 3: Disconnecting ${sockets.length} connections`);

  const disconnectStart = Date.now();
  recordEvent('disconnect_start', { count: sockets.length });

  // Disconnect all at once (measures server cleanup speed)
  sockets.forEach(s => { if (s && s.connected) s.disconnect(); });

  // Wait for all disconnect events
  await sleep(3000);

  const disconnectDuration = Date.now() - disconnectStart;
  recordEvent('disconnect_complete', { duration_ms: disconnectDuration });

  console.log(`✅ Disconnected in ${disconnectDuration}ms`);
  console.log(`   Total disconnect events received: ${metrics.disconnects}`);
}

// ─── Main ────────────────────────────────────────────────────────────────────────

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function main() {
  console.log('🚀 WebSocket Stress Test');
  console.log(`   Server: ${BASE_URL}`);
  console.log(`   Max connections: ${Math.min(200, tokens.length)}`);

  const totalStart = Date.now();

  try {
    const sockets = await scenario1_ramp();
    await scenario2_hold(sockets);
    await scenario3_disconnect(sockets);
  } catch (err) {
    console.error('❌ Test error:', err);
  }

  const totalDuration = Date.now() - totalStart;

  // ─── Results ──────────────────────────────────────────────────────────────────

  const results = {
    timestamp: new Date().toISOString(),
    total_duration_ms: totalDuration,
    connections: {
      attempted: Math.min(200, tokens.length),
      successful: metrics.successful,
      failed: metrics.failed,
      timeouts: metrics.timeouts,
      errors: metrics.errors,
    },
    connect_time: {
      p50: percentile(metrics.connectTimes, 50),
      p75: percentile(metrics.connectTimes, 75),
      p95: percentile(metrics.connectTimes, 95),
      p99: percentile(metrics.connectTimes, 99),
      max: Math.max(...(metrics.connectTimes.length ? metrics.connectTimes : [0])),
      min: Math.min(...(metrics.connectTimes.length ? metrics.connectTimes : [0])),
    },
    unexpected_disconnects: metrics.disconnects - Math.min(200, tokens.length),
    events_count: metrics.events.length,
  };

  console.log('\n' + '═'.repeat(50));
  console.log('📊 WEBSOCKET STRESS TEST RESULTS');
  console.log('═'.repeat(50));
  console.log(JSON.stringify(results, null, 2));

  // Write results
  const resultsFile = path.join(RESULTS_DIR, `websocket_${Date.now()}.json`);
  fs.writeFileSync(resultsFile, JSON.stringify({ results, events: metrics.events }, null, 2));
  console.log(`\n💾 Results saved to: ${resultsFile}`);

  // Verdict
  const p95 = results.connect_time.p95;
  const errorRate = results.connections.failed / results.connections.attempted;
  console.log('\n🏁 VERDICT:');
  if (p95 < 500 && errorRate < 0.01) {
    console.log('   ✅ FINE — p95 < 500ms, error rate < 1%');
  } else if (p95 < 3000 && errorRate < 0.10) {
    console.log('   ⚠️  SLOWS DOWN — p95 between 500ms-3s or error rate 1-10%');
  } else {
    console.log('   ❌ CRASHES — p95 > 3s or error rate > 10%');
  }
}

main().catch(console.error).finally(() => process.exit(0));
