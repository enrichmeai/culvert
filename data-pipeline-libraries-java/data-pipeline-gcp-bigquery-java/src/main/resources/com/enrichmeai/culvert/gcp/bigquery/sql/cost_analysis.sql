-- Culvert cost-analysis query pack (T13.4)
-- Each block is preceded by "-- query: <name>" and ends at the next such marker
-- or end-of-file. Use CostAnalysisQueries.loadQuery(name) to retrieve a block.
--
-- Table: cost_metrics (see BigQueryFinOpsSink for schema)
-- All queries target the BigQuery Standard SQL dialect.

-- query: cost_by_run
SELECT
    run_id,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd,
    SUM(slot_millis)             AS total_slot_millis
FROM cost_metrics
GROUP BY run_id
ORDER BY total_estimated_cost_usd DESC;

-- query: cost_by_stage
SELECT
    label.value                  AS stage,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd
FROM cost_metrics, UNNEST(labels) AS label
WHERE label.key = 'stage'
GROUP BY stage
ORDER BY total_estimated_cost_usd DESC;

-- query: top_expensive_runs_7d
SELECT
    run_id,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd,
    MIN(`timestamp`)             AS earliest,
    MAX(`timestamp`)             AS latest
FROM cost_metrics
WHERE `timestamp` >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY run_id
ORDER BY total_estimated_cost_usd DESC
LIMIT 10;

-- query: budget_breach_log
SELECT
    run_id,
    estimated_cost_usd,
    system,
    environment,
    cost_center,
    owner,
    `timestamp`
FROM cost_metrics
WHERE estimated_cost_usd > ?
ORDER BY `timestamp` DESC;
