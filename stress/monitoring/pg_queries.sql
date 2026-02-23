-- PostgreSQL Live Monitoring Queries
-- =====================================
-- Run these during stress tests to observe DB behavior in real-time.
--
-- Usage:
--   psql -d tms_messaging -f stress/monitoring/pg_queries.sql
--
-- Or run individual queries as needed in a separate psql session:
--   watch -n 1 'psql -d tms_messaging -c "<query>"'
--
-- ─────────────────────────────────────────────────────────────────────────────
-- TIP: Run each section in a separate terminal during the specific test phase.
-- ─────────────────────────────────────────────────────────────────────────────


-- ═══════════════════════════════════════════════════════════════
-- 1. CONNECTION POOL STATUS (Run during ALL tests)
-- ═══════════════════════════════════════════════════════════════
-- SQLAlchemy pool: pool_size=20 + max_overflow=10 = 30 max connections
-- When active >= 30: DB pool exhausted → 503 errors start

\echo '=== 1. CONNECTION POOL STATUS ==='
SELECT
    state,
    count(*) AS connection_count,
    ROUND(count(*) * 100.0 / 30, 1) AS pct_of_30_pool
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state
ORDER BY state;


-- ═══════════════════════════════════════════════════════════════
-- 2. LOCK QUEUE DEPTH (Critical during poll_vote.js test)
-- ═══════════════════════════════════════════════════════════════
-- poll_service.py:194 uses SELECT ... WITH FOR UPDATE
-- Concurrent voters queue up waiting for the row lock.
-- Lock wait count > 5 = performance degradation starting
-- Lock wait count > 20 = significant slowdown

\echo ''
\echo '=== 2. LOCK QUEUE DEPTH (poll test) ==='
SELECT
    count(*) AS sessions_waiting_on_locks,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE wait_event_type = 'Lock'
  AND datname = current_database()
GROUP BY wait_event_type, wait_event
ORDER BY sessions_waiting_on_locks DESC;


-- ═══════════════════════════════════════════════════════════════
-- 3. ACTIVE QUERIES (What is the DB actually doing right now?)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 3. ACTIVE QUERIES (last 5s) ==='
SELECT
    pid,
    state,
    wait_event_type,
    wait_event,
    ROUND(EXTRACT(EPOCH FROM (now() - query_start)) * 1000) AS query_ms,
    LEFT(query, 100) AS query_snippet
FROM pg_stat_activity
WHERE datname = current_database()
  AND state != 'idle'
  AND query_start > now() - interval '5 seconds'
ORDER BY query_ms DESC
LIMIT 20;


-- ═══════════════════════════════════════════════════════════════
-- 4. LONG-RUNNING QUERIES (Timeout indicator)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 4. LONG-RUNNING QUERIES (> 1s) ==='
SELECT
    pid,
    state,
    ROUND(EXTRACT(EPOCH FROM (now() - query_start)) * 1000) AS running_ms,
    LEFT(query, 150) AS query
FROM pg_stat_activity
WHERE datname = current_database()
  AND state != 'idle'
  AND query_start < now() - interval '1 second'
ORDER BY running_ms DESC;


-- ═══════════════════════════════════════════════════════════════
-- 5. POLL LOCK CONTENTION (During poll_vote.js)
-- ═══════════════════════════════════════════════════════════════
-- Shows which poll row is contended and who's waiting

\echo ''
\echo '=== 5. POLL LOCK CONTENTION ==='
SELECT
    blocked.pid AS blocked_pid,
    blocked.query_start,
    ROUND(EXTRACT(EPOCH FROM (now() - blocked.query_start)) * 1000) AS blocked_ms,
    blocker.pid AS blocker_pid,
    LEFT(blocked.query, 80) AS blocked_query,
    LEFT(blocker.query, 80) AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocker ON blocker.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.datname = current_database()
  AND blocked.query ILIKE '%polls%'
ORDER BY blocked_ms DESC
LIMIT 10;


-- ═══════════════════════════════════════════════════════════════
-- 6. TABLE I/O STATS (Spot the debug query full-table scan)
-- ═══════════════════════════════════════════════════════════════
-- The debug query in message_repo.py:164 triggers seq scans.
-- High seq_scan count on 'messages' table = debug query is running.
-- seq_tup_read / seq_scan = average rows per scan (should be 50, not 500+)

\echo ''
\echo '=== 6. TABLE SCAN STATS (messages table) ==='
SELECT
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    CASE WHEN seq_scan > 0 THEN seq_tup_read / seq_scan ELSE 0 END AS avg_rows_per_scan,
    idx_scan,
    n_live_tup AS live_rows
FROM pg_stat_user_tables
WHERE relname IN ('messages', 'polls', 'poll_votes', 'message_reactions')
ORDER BY seq_tup_read DESC;


-- ═══════════════════════════════════════════════════════════════
-- 7. POLL VOTES PROGRESS (During poll_vote.js)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 7. POLL VOTE COUNTS ==='
SELECT
    po.text AS option_text,
    COUNT(pv.id) AS vote_count,
    ROUND(COUNT(pv.id) * 100.0 / NULLIF(SUM(COUNT(pv.id)) OVER (), 0), 1) AS pct
FROM poll_options po
LEFT JOIN poll_votes pv ON pv.option_id = po.id
GROUP BY po.id, po.text
ORDER BY vote_count DESC;


-- ═══════════════════════════════════════════════════════════════
-- 8. REACTION ACCUMULATION (During reactions.js)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 8. REACTION STATS ==='
SELECT
    COUNT(*) AS total_reactions,
    COUNT(DISTINCT message_id) AS messages_with_reactions,
    ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT message_id), 0), 1) AS avg_per_message,
    MAX(reaction_count) AS max_reactions_on_one_message
FROM (
    SELECT message_id, COUNT(*) AS reaction_count
    FROM message_reactions
    GROUP BY message_id
) sub
CROSS JOIN (SELECT COUNT(*) AS total_reactions FROM message_reactions) totals;


-- ═══════════════════════════════════════════════════════════════
-- 9. MESSAGE STATS (Verify seeding worked)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 9. MESSAGE STATS BY TYPE ==='
SELECT
    type,
    COUNT(*) AS count,
    COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) AS active_count
FROM messages
GROUP BY type
ORDER BY count DESC;


-- ═══════════════════════════════════════════════════════════════
-- 10. DATABASE SIZE (Monitor growth during test)
-- ═══════════════════════════════════════════════════════════════

\echo ''
\echo '=== 10. DATABASE SIZE ==='
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS data_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size,
    n_live_tup AS live_rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;


-- ═══════════════════════════════════════════════════════════════
-- 11. ADVISORY LOCKS (Message send test)
-- ═══════════════════════════════════════════════════════════════
-- pg_advisory_xact_lock serializes message sends per conversation.
-- If many sessions hold advisory locks, message sending is serialized.

\echo ''
\echo '=== 11. ADVISORY LOCKS (message send test) ==='
SELECT
    pid,
    granted,
    locktype,
    classid,
    objid AS lock_key,
    mode
FROM pg_locks
WHERE locktype = 'advisory'
ORDER BY granted DESC, pid;


-- ═══════════════════════════════════════════════════════════════
-- 12. RESET POLL VOTES (After each poll test run)
-- ═══════════════════════════════════════════════════════════════
-- Uncomment and run between test scenarios:

-- DELETE FROM poll_votes
-- WHERE option_id IN (
--     SELECT po.id FROM poll_options po
--     JOIN polls p ON p.id = po.poll_id
--     JOIN messages m ON m.id = p.message_id
--     JOIN conversations c ON c.id = m.conversation_id
--     WHERE c.name = 'Stress Test Group'
-- );
-- \echo 'Poll votes cleared'


-- ═══════════════════════════════════════════════════════════════
-- LIVE MONITORING SCRIPT (Run in a loop during tests)
-- ═══════════════════════════════════════════════════════════════
-- Save this to a file and run: watch -n 2 psql -d tms_messaging -f monitoring.sql
--
-- Example one-liner for connection pool monitoring:
-- watch -n 1 "psql -d tms_messaging -c \"SELECT state, count(*) FROM pg_stat_activity WHERE datname='tms_messaging' GROUP BY state\""
--
-- Example for lock depth:
-- watch -n 1 "psql -d tms_messaging -c \"SELECT count(*) as waiting FROM pg_stat_activity WHERE wait_event_type='Lock' AND datname='tms_messaging'\""
