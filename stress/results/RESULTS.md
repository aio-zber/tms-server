# Stress Test Results

> **Date**: _Fill in after running tests_
> **Server**: tms-server (FastAPI + PostgreSQL + Redis)
> **Client**: tms-client (Next.js 14)
> **Environment**: _local / staging / production_

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| DB Pool | pool_size=20, max_overflow=10 (30 total) |
| Rate Limit | _disabled for tests_ |
| Server | http://localhost:8000 |
| Client | http://localhost:3000 |
| Test Users | 100 seeded users |
| Group Conversation | 100 IMAGE + 100 FILE + 1 POLL |

---

## Test A: Poll Concurrent Voting

**Bottleneck**: `poll_service.py:194` — `SELECT ... WITH FOR UPDATE`

| Scenario | VUs | p50 | p95 | p99 | Error Rate | Verdict |
|----------|-----|-----|-----|-----|------------|---------|
| Warm-up | 10 | _ms | _ms | _ms | _% | |
| Ramp | 30 | _ms | _ms | _ms | _% | |
| Stress | 50 | _ms | _ms | _ms | _% | |
| Extreme | 100 | _ms | _ms | _ms | _% | |

**PostgreSQL Lock Queue (peak)**:
- Sessions waiting on locks: _
- Max lock wait time: _ms
- Pool exhausted at: _ VUs

**Verdict**: ☐ Fine ☐ Slows Down ☐ Crashes

**Root cause**: _Fill in_

---

## Test B: Reactions

**Bottleneck**: `selectinload(Message.reactions)` loads all rows per page

### Phase 1: Write (100 VUs × 5 reactions)

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| p95 latency | _ms | < 500ms | |
| p99 latency | _ms | < 1000ms | |
| Error rate | _% | < 5% | |
| Total reactions written | _ | 500 | |

### Phase 2: Read (50 VUs, pages with heavy reactions)

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| p95 latency | _ms | < 3000ms | |
| Avg payload size | _KB | | |
| Rows loaded per page | _ | | |
| Error rate | _% | < 5% | |

**Verdict**: Write ☐ Fine ☐ Slows Down ☐ Crashes | Read ☐ Fine ☐ Slows Down ☐ Crashes

---

## Test C: Media Messages

**Bottleneck**: Debug query in `message_repo.py:164–182` (unbounded SELECT *)

### Scenario 1: Concurrent Open (50 VUs)

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| p95 latency | _ms | < 5000ms | |
| p99 latency | _ms | < 10000ms | |
| Avg payload size | _KB | | |
| Error rate | _% | < 5% | |

### Scenario 2: Pagination (20 VUs × 5 pages)

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| p95 latency | _ms | < 3000ms | |
| Error rate | _% | < 5% | |

**DB Scan Stats (from pg_queries.sql)**:
- `seq_scan` on messages: _
- `avg_rows_per_scan`: _ (expected: 50, actual if debug query active: _)

**Verdict**: ☐ Fine ☐ Slows Down ☐ Crashes

---

## Test D: File Listing

**Bottleneck**: Debug query + HMAC signing for 100 ossKeys per request

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| p95 latency (30 VUs) | _ms | < 5000ms | |
| p99 latency | _ms | < 10000ms | |
| Throughput | _ req/s | | |
| Breaking point (ramp) | _ VUs | | |
| Error rate | _% | < 5% | |

**Verdict**: ☐ Fine ☐ Slows Down ☐ Crashes

---

## Test E: Message Send (Advisory Lock)

**Validates**: Per-conversation advisory lock scales horizontally

| Scenario | VUs | Conversations | p50 | p95 | Throughput | Verdict |
|----------|-----|--------------|-----|-----|------------|---------|
| Single conv | 50 | 1 | _ms | _ms | _ msg/s | |
| Distributed | 50 | 10 | _ms | _ms | _ msg/s | |
| Speedup ratio | | | | | _× | |

**Expected**: Distributed should be ~10× faster than single.

**Verdict**: ☐ Correct (distributed faster) ☐ Incorrect

---

## WebSocket Connections

**Bottleneck**: Each connect triggers `SELECT conversation_ids WHERE user_id=?` — 200 concurrent queries hit 30-pool limit

| Metric | Value | Target |
|--------|-------|--------|
| Connect p50 | _ms | < 200ms |
| Connect p95 | _ms | < 1000ms |
| Connect p99 | _ms | < 3000ms |
| Successful connections | _/200 | 200 |
| Failed connections | _ | 0 |
| Timeouts | _ | 0 |
| Unexpected drops (hold) | _ | 0 |
| Disconnect cleanup time | _ms | < 5000ms |

**Verdict**: ☐ Fine ☐ Slows Down ☐ Crashes

---

## Browser Performance (Playwright)

**Bottleneck**: MessageList.tsx renders all messages in DOM (no react-window virtualization)

| Metric | 50 messages | 100 messages | 150 messages | Targets |
|--------|------------|--------------|--------------|---------|
| LCP | _ms | — | — | < 2500ms |
| DOM nodes | _ | _ | _ | < 8k / < 20k |
| JS heap | _MB | _MB | _MB | < 60MB / < 150MB |
| FPS (avg) | _ | _ | _ | > 50 / > 20 |
| FPS (min) | _ | _ | _ | |
| Load time | _ms | _ms | _ms | |

**E2EE Sequential Decryption**:
- 50 messages decryption time: _ms (target: < 400ms)

**Verdict**: ☐ Fine ☐ Slows Down ☐ Crashes

---

## Summary

| Test | Verdict | Root Cause | Fix |
|------|---------|------------|-----|
| Poll voting (≤15 VUs) | | | |
| Poll voting (31+ VUs) | | `with_for_update()` lock | Optimistic locking |
| Reaction write | | | |
| Reaction read (heavy) | | `selectinload` all rows | Pre-aggregate counts |
| Media fetch | | Debug query full-scan | Remove debug query |
| File listing | | Debug query + HMAC | Remove debug query |
| WebSocket 200 conns | | 200 concurrent DB queries | Connection caching |
| Browser 50 msgs | | | |
| Browser 150 msgs | | No virtualization | Use react-window |

---

## Priority Fix List

1. **CRITICAL** — Remove `debug_query` block in `message_repo.py:164–182`
   - Estimated impact: -50% DB load on all message endpoints
   - Effort: 10 minutes

2. **HIGH** — Replace `with_for_update()` in `poll_service.py:194`
   - Estimated impact: Unblocks 31+ concurrent voters
   - Effort: 2-4 hours

3. **HIGH** — Implement `react-window` in `MessageList.tsx:332`
   - Estimated impact: Consistent 60fps regardless of message count
   - Effort: 4-8 hours

4. **MEDIUM** — Pre-aggregate reaction counts
   - Estimated impact: Eliminates selectinload N+1 problem
   - Effort: 1-2 days (requires migration)
