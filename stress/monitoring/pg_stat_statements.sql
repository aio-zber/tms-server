-- pg_stat_statements Query Analysis
-- =====================================
-- Requirement 3: Database query time p95 < 100ms
--
-- Run this AFTER a stress test run to see actual query latencies.
--
-- Prerequisites (run once on staging RDS):
--   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
--   -- Also add to postgresql.conf / parameter group:
--   shared_preload_libraries = 'pg_stat_statements'   (requires reboot)
--
-- Reset stats before each test run for clean numbers:
--   SELECT pg_stat_statements_reset();
--
-- Usage:
--   psql $DATABASE_URL_SYNC -f stress/monitoring/pg_stat_statements.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- ═══════════════════════════════════════════════════════════════
-- 1. REQUIREMENT 3 GATE: Queries exceeding 100ms mean
--    If any rows appear here → Requirement 3 FAILS for that query.
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== REQUIREMENT 3: Queries with mean > 100ms (FAIL if any rows) ==='
SELECT
    calls,
    ROUND(mean_exec_time::numeric, 2)                                       AS mean_ms,
    ROUND((mean_exec_time + 1.645 * stddev_exec_time)::numeric, 2)          AS approx_p95_ms,
    ROUND(max_exec_time::numeric, 2)                                        AS max_ms,
    LEFT(query, 140)                                                        AS query_snippet
FROM pg_stat_statements
WHERE mean_exec_time > 100
  AND query NOT ILIKE '%pg_stat%'
  AND calls > 5
ORDER BY mean_exec_time DESC;


-- ═══════════════════════════════════════════════════════════════
-- 2. TOP 20 SLOWEST QUERIES (mean exec time)
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== TOP 20 SLOWEST QUERIES (by mean_exec_time) ==='
SELECT
    calls,
    ROUND(mean_exec_time::numeric, 2)                                       AS mean_ms,
    ROUND((mean_exec_time + 1.645 * stddev_exec_time)::numeric, 2)          AS approx_p95_ms,
    ROUND(max_exec_time::numeric, 2)                                        AS max_ms,
    ROUND(rows::numeric / NULLIF(calls, 0), 1)                              AS avg_rows,
    LEFT(query, 120)                                                        AS query_snippet
FROM pg_stat_statements
WHERE query NOT ILIKE '%pg_stat%'
  AND calls > 5
ORDER BY mean_exec_time DESC
LIMIT 20;


-- ═══════════════════════════════════════════════════════════════
-- 3. TOP TOTAL TIME CONSUMERS (hottest queries under load)
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== TOP 10 QUERIES BY TOTAL EXECUTION TIME ==='
SELECT
    calls,
    ROUND(total_exec_time::numeric, 0)                                      AS total_ms,
    ROUND(mean_exec_time::numeric, 2)                                       AS mean_ms,
    LEFT(query, 120)                                                        AS query_snippet
FROM pg_stat_statements
WHERE query NOT ILIKE '%pg_stat%'
ORDER BY total_exec_time DESC
LIMIT 10;


-- ═══════════════════════════════════════════════════════════════
-- 4. CONNECTION POOL UTILIZATION DURING TEST
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== CURRENT CONNECTION POOL STATUS (pool_size=20, max_overflow=10) ==='
SELECT
    state,
    COUNT(*)                                                                AS connections,
    ROUND(COUNT(*) * 100.0 / 30, 1)                                        AS pct_of_30_pool
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state
ORDER BY state;


-- ═══════════════════════════════════════════════════════════════
-- 5. MESSAGES TABLE SCAN STATS
--    High seq_scan + high avg_rows_per_scan = debug/unbounded query
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== TABLE SCAN STATS (messages, polls, reactions) ==='
SELECT
    relname                                                                  AS table_name,
    seq_scan,
    seq_tup_read,
    CASE WHEN seq_scan > 0
         THEN seq_tup_read / seq_scan
         ELSE 0 END                                                         AS avg_rows_per_seq_scan,
    idx_scan,
    n_live_tup                                                              AS live_rows
FROM pg_stat_user_tables
WHERE relname IN ('messages', 'polls', 'poll_votes', 'message_reactions', 'message_statuses')
ORDER BY seq_tup_read DESC;


-- ═══════════════════════════════════════════════════════════════
-- 6. REQUIREMENT 3 SUMMARY LINE
-- ═══════════════════════════════════════════════════════════════
\echo ''
\echo '=== REQUIREMENT 3 SUMMARY ==='
SELECT
    CASE
        WHEN COUNT(*) = 0 THEN '✅ PASS — no queries with mean > 100ms'
        ELSE CONCAT('❌ FAIL — ', COUNT(*), ' query type(s) exceed 100ms mean')
    END AS requirement_3_verdict,
    ROUND(MAX(mean_exec_time)::numeric, 2)         AS worst_mean_ms,
    ROUND(MAX(mean_exec_time + 1.645 * stddev_exec_time)::numeric, 2) AS worst_approx_p95_ms
FROM pg_stat_statements
WHERE mean_exec_time > 100
  AND query NOT ILIKE '%pg_stat%'
  AND calls > 5;
