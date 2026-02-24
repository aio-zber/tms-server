/**
 * Test: File Upload (100MB with progress)
 * =========================================
 * Requirement 4: Support 100MB file uploads.
 *
 * Three scenarios:
 *   A. baseline_upload  — 1KB files, 5 VUs × 30s (proves endpoint works)
 *   B. large_file_upload — 100MB file, 2 VUs × 5 min (the actual requirement)
 *   C. concurrent_uploads — 10MB files, 5 VUs × 2 min (parallel streams)
 *
 * Progress tracking via k6 built-in timings:
 *   res.timings.sending  = time uploading bytes (network transit phase)
 *   res.timings.waiting  = server processing + OSS push (after last byte received)
 *   res.timings.duration = total (user-perceived time)
 *
 * If 100MB in-memory causes OOM, pre-generate a binary file:
 *   dd if=/dev/urandom of=stress/data/test_100mb.bin bs=1M count=100
 * Then set: FILE_FROM_DISK=1
 *
 * Run:
 *   k6 run -e BASE_URL=https://tms-chat-staging.hotelsogo-ai.com stress/backend/file_upload.js
 *   k6 run -e BASE_URL=... -e FILE_SIZE_MB=10 stress/backend/file_upload.js  # smoke test
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const BASE_URL      = __ENV.BASE_URL      || 'https://tms-chat-staging.hotelsogo-ai.com';
const FILE_SIZE_MB  = parseInt(__ENV.FILE_SIZE_MB  || '100', 10);
const FILE_FROM_DISK = __ENV.FILE_FROM_DISK === '1';

const FILE_SIZE_BYTES   = FILE_SIZE_MB * 1024 * 1024;
const MEDIUM_SIZE_BYTES = 10 * 1024 * 1024;
const SMALL_SIZE_BYTES  = 1024;

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('../data/tokens_array.json'));
});
const convData = new SharedArray('conversations', function () {
  return [JSON.parse(open('../data/conversation_ids.json'))];
});

// ─── Build file buffers in init context ──────────────────────────────────────
// Runs once per VU before scenarios start. A repeating pattern avoids
// crypto overhead while still being a valid binary payload.

function makeFileBuffer(sizeBytes) {
  if (FILE_FROM_DISK && sizeBytes === FILE_SIZE_BYTES) {
    // Read pre-generated binary from disk (avoids JS heap allocation)
    // Generate with: dd if=/dev/urandom of=stress/data/test_100mb.bin bs=1M count=100
    try {
      return open('../data/test_100mb.bin', 'b');
    } catch (e) {
      console.warn('test_100mb.bin not found, falling back to in-memory buffer.');
    }
  }
  const chunk = new Uint8Array(4096);
  for (let i = 0; i < 4096; i++) chunk[i] = i % 256;
  const buf = new Uint8Array(sizeBytes);
  for (let offset = 0; offset < sizeBytes; offset += 4096) {
    const len = Math.min(4096, sizeBytes - offset);
    buf.set(chunk.subarray(0, len), offset);
  }
  return buf.buffer;
}

const largeFileBuffer  = makeFileBuffer(FILE_SIZE_BYTES);
const mediumFileBuffer = makeFileBuffer(MEDIUM_SIZE_BYTES);
const smallFileBuffer  = makeFileBuffer(SMALL_SIZE_BYTES);

// ─── Custom Metrics ──────────────────────────────────────────────────────────
const uploadTotalMs   = new Trend('upload_total_ms',   true);
const uploadSendingMs = new Trend('upload_sending_ms', true);  // transit
const uploadWaitingMs = new Trend('upload_waiting_ms', true);  // server processing
const uploadErrors    = new Rate('upload_errors');
const uploadSuccess   = new Counter('uploads_success');

export const options = {
  scenarios: {
    // A: prove the endpoint works with tiny files
    baseline_upload: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      exec: 'uploadSmallFile',
    },

    // B: the actual requirement — 100MB upload
    // 2 VUs only: each holds FILE_SIZE_MB in memory
    large_file_upload: {
      executor: 'constant-vus',
      vus: 2,
      duration: '300s',
      startTime: '40s',
      exec: 'uploadLargeFile',
    },

    // C: parallel 10MB streams — tests concurrent upload pipeline
    concurrent_uploads: {
      executor: 'constant-vus',
      vus: 5,
      duration: '120s',
      startTime: '40s',
      exec: 'uploadMediumFile',
    },
  },

  thresholds: {
    // Large file: generous timeout — 300s for 100MB over WAN is the ceiling
    'upload_total_ms{scenario:large_file_upload}': [
      { threshold: 'p(95)<300000', abortOnFail: false },
    ],
    // Baseline 1KB must be fast
    'upload_total_ms{scenario:baseline_upload}': [
      { threshold: 'p(95)<5000', abortOnFail: false },
    ],
    upload_errors:   [{ threshold: 'rate<0.05', abortOnFail: false }],
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: false }],
  },
};

export function setup() {
  const convId = convData[0].group_conversation_id;
  console.log(`\n📦 File Upload Test (Requirement 4)`);
  console.log(`   Server:    ${BASE_URL}`);
  console.log(`   Endpoint:  POST /api/v1/messages/upload`);
  console.log(`   Conversation: ${convId}`);
  console.log(`   Large file: ${FILE_SIZE_MB}MB (${FILE_SIZE_BYTES.toLocaleString()} bytes)`);
  console.log(`   Source: ${FILE_FROM_DISK ? 'stress/data/test_100mb.bin (disk)' : 'in-memory buffer'}`);
  console.log(`   Scenario A: 1KB baseline,  5 VUs × 30s`);
  console.log(`   Scenario B: ${FILE_SIZE_MB}MB large,    2 VUs × 5 min`);
  console.log(`   Scenario C: 10MB concurrent, 5 VUs × 2 min\n`);
  return { convId };
}

function doUpload(data, fileBuffer, mimeType, filename, sizeLabel, sizeMB) {
  const token = tokens[__VU % tokens.length];

  const formData = {
    conversation_id: data.convId,
    file: http.file(fileBuffer, filename, mimeType),
  };

  const res = http.post(`${BASE_URL}/api/v1/messages/upload`, formData, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: '600s',  // 10 min — 100MB over staging WAN
    tags: { file_size: sizeLabel },
  });

  uploadTotalMs.add(res.timings.duration);
  uploadSendingMs.add(res.timings.sending);
  uploadWaitingMs.add(res.timings.waiting);

  const ok = check(res, {
    'upload 201':           (r) => r.status === 201,
    'response has id':      (r) => {
      try {
        const b = JSON.parse(r.body);
        return !!(b.id || b.data?.id);
      } catch (e) { return false; }
    },
  });

  if (ok) {
    uploadSuccess.add(1);
    uploadErrors.add(0);
    const throughputMBps = (sizeMB / (res.timings.duration / 1000)).toFixed(2);
    console.log(
      `VU${__VU} [${sizeLabel}] ✅ ` +
      `total=${res.timings.duration}ms ` +
      `(sending=${res.timings.sending}ms / waiting=${res.timings.waiting}ms) ` +
      `throughput=${throughputMBps} MB/s`
    );
  } else {
    uploadErrors.add(1);
    console.warn(`VU${__VU} [${sizeLabel}] ❌ ${res.status} — ${res.body?.substring(0, 200)}`);
  }
}

export function uploadLargeFile(data) {
  doUpload(
    data,
    largeFileBuffer,
    'application/octet-stream',
    `stress_${FILE_SIZE_MB}mb.bin`,
    `${FILE_SIZE_MB}MB`,
    FILE_SIZE_MB
  );
  // No sleep — measure raw sustained throughput
}

export function uploadMediumFile(data) {
  doUpload(data, mediumFileBuffer, 'application/octet-stream', 'stress_10mb.bin', '10MB', 10);
}

export function uploadSmallFile(data) {
  doUpload(data, smallFileBuffer, 'text/plain', 'stress_1kb.txt', '1KB', 0.001);
}

export function teardown() {
  console.log('\n📊 File Upload Test Complete');
  console.log('   upload_sending_ms = network transit time (bandwidth-dependent)');
  console.log('   upload_waiting_ms = server processing + OSS push (after last byte)');
  console.log('   upload_total_ms   = user-perceived duration');
  console.log(`   Throughput (MB/s) = ${FILE_SIZE_MB} / (upload_total_ms / 1000)`);
  console.log('');
  console.log('   Requirement 4 passes if:');
  console.log(`   - uploads_success > 0 for ${FILE_SIZE_MB}MB files`);
  console.log('   - No 413 (payload too large) or 500 errors on large file');
  console.log('   - upload_total_ms p95 < 300000 (5 min) — generous for 100MB over WAN');
}
