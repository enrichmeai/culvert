-- Culvert job control on PostgreSQL: the append-only ledger behind PostgresJobControlRepository.
-- Plain SQL, applied once per database (psql -f job_control.sql). It is idempotent.
-- No migration tool is chosen: Flyway, Liquibase or none is a deployment decision (#193).
--
-- One row per state change, never one row per run. Nothing UPDATEs or DELETEs this table; reads
-- rank a run's rows (terminal first, earliest terminal wins) to get its current state.

CREATE SCHEMA IF NOT EXISTS job_control;

CREATE TABLE IF NOT EXISTS job_control.pipeline_jobs (
    seq                  BIGSERIAL PRIMARY KEY,            -- ledger order; breaks updated_at ties
    run_id               TEXT             NOT NULL,
    opens_run            BOOLEAN          NOT NULL DEFAULT FALSE, -- true only on the createJob row
    system_id            TEXT             NOT NULL,
    pipeline_name        TEXT             NOT NULL,
    extract_date         DATE             NOT NULL,
    status               TEXT             NOT NULL,        -- JobStatus wire value, e.g. 'running'
    job_type             TEXT             NOT NULL,        -- JobType name, e.g. 'INGESTION'
    entity_type          TEXT,
    source_file          TEXT,
    target_table         TEXT,
    record_count         BIGINT           NOT NULL DEFAULT 0,
    error_count          BIGINT           NOT NULL DEFAULT 0,
    retry_count          INTEGER          NOT NULL DEFAULT 0,
    failure_stage        TEXT,                             -- FailureStage wire value
    error_code           TEXT,
    error_message        TEXT,
    error_file_path      TEXT,
    estimated_cost_usd   DOUBLE PRECISION NOT NULL DEFAULT 0,
    billed_bytes_scanned BIGINT           NOT NULL DEFAULT 0,
    billed_bytes_written BIGINT           NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ      NOT NULL,
    updated_at           TIMESTAMPTZ      NOT NULL,
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ
);

-- One createJob per run id, enforced by the server (unique_violation, SQLSTATE 23505).
CREATE UNIQUE INDEX IF NOT EXISTS pipeline_jobs_one_create_per_run
    ON job_control.pipeline_jobs (run_id) WHERE opens_run;

CREATE INDEX IF NOT EXISTS pipeline_jobs_run_id ON job_control.pipeline_jobs (run_id);
CREATE INDEX IF NOT EXISTS pipeline_jobs_system_date ON job_control.pipeline_jobs (system_id, extract_date);

-- StageClaim (#195): an atomic claim on one stage of one unit for one period.
-- Both tables are insert-only, like the ledger. stage_claims holds one row per key, which exists
-- only to be locked (SELECT ... FOR UPDATE). stage_completions records that the stage is done:
-- its primary key means a stage can be completed once, and a completed stage never runs again.
CREATE TABLE IF NOT EXISTS job_control.stage_claims (
    unit       TEXT        NOT NULL,
    stage      TEXT        NOT NULL,
    period     TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (unit, stage, period)
);

CREATE TABLE IF NOT EXISTS job_control.stage_completions (
    unit         TEXT        NOT NULL,
    stage        TEXT        NOT NULL,
    period       TEXT        NOT NULL,
    completed_by TEXT        NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (unit, stage, period)
);
