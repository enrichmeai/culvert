package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryError;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryParameterValue;
import com.google.cloud.bigquery.TableResult;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * {@link JobControlRepository} implementation backed by Google Cloud BigQuery.
 *
 * <p>The reference implementation of the job-control contract: the eleven
 * contract methods run as parameterised SQL against the
 * {@code job_control.pipeline_jobs} ledger, covering the full
 * {@link PipelineJob} record (pipeline_name, source_file, target_table,
 * record_count, error_count, FinOps fields).
 *
 * <p>Wraps a {@link BigQuery} client. All operations execute as parameterised
 * queries; the wrapped client is reused for every call. Like
 * {@link BigQueryWarehouse}, this class does NOT implement
 * {@link AutoCloseable} — google-cloud-bigquery 2.x's {@code BigQuery}
 * interface itself is not {@code AutoCloseable}. Consumers manage the
 * client's lifecycle.
 *
 * <p>Constructor injection: pass in a pre-built {@code BigQuery} client, the
 * GCP project ID, the dataset (default {@code job_control} in the Python
 * source), and the table (default {@code pipeline_jobs}). The fully-qualified
 * table is quoted with backticks as {@code `project.dataset.table`} in every
 * query.
 *
 * <h2>Conditional writes</h2>
 *
 * <p>Every write is a compare-and-set. BigQuery has no row lock and no
 * {@code INSERT ... IF NOT EXISTS}, but a single DML statement is atomic and
 * reports how many rows it matched, so the guard goes in the statement itself
 * and the affected-row count is the answer:
 *
 * <ul>
 *   <li>{@link #createJob} is a {@code MERGE ... WHEN NOT MATCHED THEN INSERT}
 *       — 0 affected rows means the {@code runId} already exists, and it
 *       throws rather than writing a second row for the same run.
 *   <li>Every status transition carries {@code AND status IN (...)} naming the
 *       states it may legally leave. 0 affected rows means either the wrong
 *       prior state or no row at all; both throw
 *       {@link IllegalStateException}, distinguished by a follow-up
 *       {@link #getJob} on the failure path only.
 * </ul>
 *
 * <p>The allowed prior states, from {@link #allowedPriorStates}:
 *
 * <table border="1">
 *   <caption>Permitted transitions</caption>
 *   <tr><th>Target</th><th>Allowed prior states</th></tr>
 *   <tr><td>{@code RUNNING}</td><td>{@code CREATED}, {@code RETRYING}</td></tr>
 *   <tr><td>{@code SUCCEEDED}</td><td>{@code RUNNING}</td></tr>
 *   <tr><td>{@code FAILED}</td><td>{@code CREATED}, {@code RUNNING}, {@code RETRYING}, {@code FAILED}</td></tr>
 *   <tr><td>{@code RETRYING}</td><td>{@code CREATED}, {@code RUNNING}, {@code FAILED}</td></tr>
 *   <tr><td>{@code CANCELLED}</td><td>{@code CREATED}, {@code RUNNING}, {@code RETRYING}</td></tr>
 *   <tr><td>{@code CREATED}</td><td>none — not a transition target; use {@link #createJob}</td></tr>
 * </table>
 *
 * <p>{@code FAILED -> FAILED} is the one deliberate non-progressing
 * transition. It is a live path, not an oversight: {@code QuarantineHandler}
 * marks a run FAILED when it quarantines rows, and the ingestion runner's
 * reconciliation check can then mark the same run FAILED again with a more
 * specific error code. The second call overwrites the first call's error
 * detail — pre-existing behaviour, left as it is.
 *
 * <p>Atomicity here rests on BigQuery's DML concurrency model, not on a row
 * lock: BigQuery serialises mutating DML against a single table, so the guard
 * predicate is evaluated against a state no concurrent mutation can have
 * changed underneath it. Two writers racing the same transition therefore
 * produce one winner and one {@link IllegalStateException}, not two winners.
 *
 * <p>Sprint-1 deliverable for issue #8; made conditional in Sprint 23
 * (story 1.3), which also fixes issue #99 — DML affected rows come from
 * {@code QueryStatistics.getNumDmlAffectedRows()}, not from
 * {@link TableResult#getTotalRows()}, which is 0 for a DML statement.
 */
public final class BigQueryJobControlRepository implements JobControlRepository {

    private final BigQuery client;
    private final String projectId;
    private final String dataset;
    private final String table;
    private final String fqtn;

    /**
     * Primary constructor.
     *
     * @param client    Pre-built BigQuery client. Required.
     * @param projectId GCP project ID. Required.
     * @param dataset   BigQuery dataset (e.g. {@code "job_control"}). Required.
     * @param table     BigQuery table (e.g. {@code "pipeline_jobs"}). Required.
     * @throws NullPointerException if any argument is null.
     */
    public BigQueryJobControlRepository(BigQuery client, String projectId,
                                        String dataset, String table) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.projectId = Objects.requireNonNull(projectId, "projectId must not be null");
        this.dataset = Objects.requireNonNull(dataset, "dataset must not be null");
        this.table = Objects.requireNonNull(table, "table must not be null");
        this.fqtn = "`" + projectId + "." + dataset + "." + table + "`";
    }

    /**
     * No-arg constructor for worker-side auto-config reconstruction (see
     * {@link BigQueryWarehouse#BigQueryWarehouse()}). Project + region from
     * {@code GCP_PROJECT}/{@code GCP_LOCATION}; dataset/table from
     * {@code JOB_CONTROL_DATASET}/{@code JOB_CONTROL_TABLE} (defaults
     * {@code job_control}/{@code pipeline_jobs}), via {@link BigQueryDefaults}.
     */
    public BigQueryJobControlRepository() {
        this(gateAndClient(), BigQueryDefaults.project(),
                BigQueryDefaults.jobControlDataset(), BigQueryDefaults.jobControlTable());
    }

    private static com.google.cloud.bigquery.BigQuery gateAndClient() {
        BigQueryDefaults.requireGcpSelected();
        return BigQueryDefaults.client();
    }

    /**
     * {@inheritDoc}
     *
     * <p>Insert-if-absent. Runs as a {@code MERGE ... WHEN NOT MATCHED THEN
     * INSERT}, so a {@code runId} that already has a row matches, inserts
     * nothing, and reports 0 affected rows. A plain {@code INSERT} would write
     * a second row for the same run — the defect that let a re-run duplicate
     * data.
     *
     * @throws IllegalStateException if a job with this {@code runId} already exists.
     */
    @Override
    public void createJob(PipelineJob job) {
        Objects.requireNonNull(job, "job must not be null");

        String sql = "MERGE INTO " + fqtn + " AS T "
                + "USING (SELECT @run_id AS run_id) AS S ON T.run_id = S.run_id "
                + "WHEN NOT MATCHED THEN INSERT ("
                + "run_id, system_id, pipeline_name, extract_date, status, job_type, "
                + "entity_type, source_file, target_table, "
                + "record_count, error_count, retry_count, "
                + "failure_stage, error_code, error_message, error_file_path, "
                + "estimated_cost_usd, billed_bytes_scanned, billed_bytes_written, "
                + "created_at, updated_at, started_at, completed_at"
                + ") VALUES ("
                + "@run_id, @system_id, @pipeline_name, @extract_date, @status, @job_type, "
                + "@entity_type, @source_file, @target_table, "
                + "@record_count, @error_count, @retry_count, "
                + "@failure_stage, @error_code, @error_message, @error_file_path, "
                + "@estimated_cost_usd, @billed_bytes_scanned, @billed_bytes_written, "
                + "CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), @started_at, @completed_at"
                + ")";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(job.runId()))
                .addNamedParameter("system_id", QueryParameterValue.string(job.systemId()))
                .addNamedParameter("pipeline_name", QueryParameterValue.string(job.pipelineName()))
                .addNamedParameter("extract_date", QueryParameterValue.date(job.extractDate().toString()))
                .addNamedParameter("status", QueryParameterValue.string(job.status().getValue()))
                .addNamedParameter("job_type", QueryParameterValue.string(job.jobType().name()))
                .addNamedParameter("entity_type", QueryParameterValue.string(job.entityType().orElse(null)))
                .addNamedParameter("source_file", QueryParameterValue.string(job.sourceFile().orElse(null)))
                .addNamedParameter("target_table", QueryParameterValue.string(job.targetTable().orElse(null)))
                .addNamedParameter("record_count", QueryParameterValue.int64(job.recordCount()))
                .addNamedParameter("error_count", QueryParameterValue.int64(job.errorCount()))
                .addNamedParameter("retry_count", QueryParameterValue.int64((long) job.retryCount()))
                .addNamedParameter("failure_stage",
                        QueryParameterValue.string(job.failureStage().map(FailureStage::getValue).orElse(null)))
                .addNamedParameter("error_code", QueryParameterValue.string(job.errorCode().orElse(null)))
                .addNamedParameter("error_message", QueryParameterValue.string(job.errorMessage().orElse(null)))
                .addNamedParameter("error_file_path", QueryParameterValue.string(job.errorFilePath().orElse(null)))
                .addNamedParameter("estimated_cost_usd",
                        QueryParameterValue.float64(job.estimatedCostUsd()))
                .addNamedParameter("billed_bytes_scanned",
                        QueryParameterValue.int64(job.billedBytesScanned()))
                .addNamedParameter("billed_bytes_written",
                        QueryParameterValue.int64(job.billedBytesWritten()))
                .addNamedParameter("started_at",
                        QueryParameterValue.timestamp(toTimestampMicros(job.startedAt())))
                .addNamedParameter("completed_at",
                        QueryParameterValue.timestamp(toTimestampMicros(job.completedAt())))
                .build();

        if (runDml(config, "createJob") == 0L) {
            throw new IllegalStateException(
                    "createJob affected no rows: a job with runId=" + job.runId()
                            + " already exists");
        }
    }

    @Override
    public Optional<PipelineJob> getJob(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");

        String sql = "SELECT * FROM " + fqtn + " WHERE run_id = @run_id";
        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(runId))
                .build();

        TableResult result = runQuery(config, "getJob");
        for (FieldValueList row : result.iterateAll()) {
            return Optional.of(rowToPipelineJob(row));
        }
        return Optional.empty();
    }

    /**
     * {@inheritDoc}
     *
     * <p>Compare-and-set: the states this transition may legally leave are in
     * the {@code WHERE} clause, so a transition from the wrong prior state
     * matches no row and is rejected instead of silently passing.
     *
     * @throws IllegalArgumentException if {@code status} is
     *                                  {@link JobStatus#CREATED} — a job enters
     *                                  that state only via {@link #createJob}.
     * @throws IllegalStateException    if no row exists for {@code runId}, or its
     *                                  status is not one of the allowed prior
     *                                  states for {@code status}.
     */
    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(totalRecords, "totalRecords must not be null");

        Set<JobStatus> allowed = allowedPriorStates(status);
        Map<String, QueryParameterValue> priorParams = new LinkedHashMap<>();
        String guard = priorStatePredicate(allowed, priorParams);

        // Three SQL flavours per the Python source: RUNNING stamps started_at,
        // SUCCEEDED stamps completed_at + record_count, everything else just
        // bumps status + updated_at. All three carry the same prior-state guard.
        String sql;
        QueryJobConfiguration.Builder builder;
        if (status == JobStatus.RUNNING) {
            sql = "UPDATE " + fqtn + " SET status = @status, "
                    + "started_at = CURRENT_TIMESTAMP(), updated_at = CURRENT_TIMESTAMP() "
                    + "WHERE run_id = @run_id" + guard;
            builder = QueryJobConfiguration.newBuilder(sql);
        } else if (status == JobStatus.SUCCEEDED) {
            sql = "UPDATE " + fqtn + " SET status = @status, "
                    + "completed_at = CURRENT_TIMESTAMP(), record_count = @record_count, "
                    + "updated_at = CURRENT_TIMESTAMP() "
                    + "WHERE run_id = @run_id" + guard;
            builder = QueryJobConfiguration.newBuilder(sql)
                    .addNamedParameter("record_count",
                            QueryParameterValue.int64(totalRecords.orElse(0L)));
        } else {
            sql = "UPDATE " + fqtn + " SET status = @status, "
                    + "updated_at = CURRENT_TIMESTAMP() "
                    + "WHERE run_id = @run_id" + guard;
            builder = QueryJobConfiguration.newBuilder(sql);
        }

        builder.addNamedParameter("run_id", QueryParameterValue.string(runId))
                .addNamedParameter("status", QueryParameterValue.string(status.getValue()));
        priorParams.forEach(builder::addNamedParameter);
        applyTransition(builder.build(), "updateStatus", runId, allowed);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Compare-and-set on the prior state, which must be one of
     * {@code CREATED}, {@code RUNNING}, {@code RETRYING} or {@code FAILED}. A
     * run that already {@code SUCCEEDED} cannot be re-marked failed.
     *
     * @throws IllegalStateException if no row exists for {@code runId}, or its
     *                               status is not an allowed prior state.
     */
    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(errorCode, "errorCode must not be null");
        Objects.requireNonNull(errorMessage, "errorMessage must not be null");
        Objects.requireNonNull(failureStage, "failureStage must not be null");
        Objects.requireNonNull(errorFilePath, "errorFilePath must not be null");

        Set<JobStatus> allowed = allowedPriorStates(JobStatus.FAILED);
        Map<String, QueryParameterValue> priorParams = new LinkedHashMap<>();
        String guard = priorStatePredicate(allowed, priorParams);

        String sql = "UPDATE " + fqtn + " SET status = @status, "
                + "error_code = @error_code, error_message = @error_message, "
                + "failure_stage = @failure_stage, error_file_path = @error_file_path, "
                + "completed_at = CURRENT_TIMESTAMP(), updated_at = CURRENT_TIMESTAMP() "
                + "WHERE run_id = @run_id" + guard;

        QueryJobConfiguration.Builder builder = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(runId))
                .addNamedParameter("status", QueryParameterValue.string(JobStatus.FAILED.getValue()))
                .addNamedParameter("error_code", QueryParameterValue.string(errorCode))
                .addNamedParameter("error_message", QueryParameterValue.string(errorMessage))
                .addNamedParameter("failure_stage", QueryParameterValue.string(failureStage.getValue()))
                .addNamedParameter("error_file_path",
                        QueryParameterValue.string(errorFilePath.orElse(null)));
        priorParams.forEach(builder::addNamedParameter);
        applyTransition(builder.build(), "markFailed", runId, allowed);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Compare-and-set on the prior state, which must be one of
     * {@code CREATED}, {@code RUNNING} or {@code FAILED}. Retrying a run that
     * already {@code SUCCEEDED} is exactly how a re-run duplicates data, so it
     * is rejected.
     *
     * @throws IllegalStateException if no row exists for {@code runId}, or its
     *                               status is not an allowed prior state.
     */
    @Override
    public void markRetrying(String runId, int retryCount) {
        Objects.requireNonNull(runId, "runId must not be null");
        if (retryCount < 0) {
            throw new IllegalArgumentException("retryCount must be >= 0, got " + retryCount);
        }

        Set<JobStatus> allowed = allowedPriorStates(JobStatus.RETRYING);
        Map<String, QueryParameterValue> priorParams = new LinkedHashMap<>();
        String guard = priorStatePredicate(allowed, priorParams);

        String sql = "UPDATE " + fqtn + " SET status = @status, "
                + "retry_count = @retry_count, updated_at = CURRENT_TIMESTAMP() "
                + "WHERE run_id = @run_id" + guard;

        QueryJobConfiguration.Builder builder = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(runId))
                .addNamedParameter("status",
                        QueryParameterValue.string(JobStatus.RETRYING.getValue()))
                .addNamedParameter("retry_count", QueryParameterValue.int64((long) retryCount));
        priorParams.forEach(builder::addNamedParameter);
        applyTransition(builder.build(), "markRetrying", runId, allowed);
    }

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId must not be null");

        String sql;
        QueryJobConfiguration.Builder builder;
        if (systemId.isPresent()) {
            sql = "SELECT * FROM " + fqtn + " "
                    + "WHERE status IN (@created, @running) AND system_id = @system_id "
                    + "ORDER BY created_at";
            builder = QueryJobConfiguration.newBuilder(sql)
                    .addNamedParameter("system_id", QueryParameterValue.string(systemId.get()));
        } else {
            sql = "SELECT * FROM " + fqtn + " "
                    + "WHERE status IN (@created, @running) "
                    + "ORDER BY created_at";
            builder = QueryJobConfiguration.newBuilder(sql);
        }

        QueryJobConfiguration config = builder
                .addNamedParameter("created", QueryParameterValue.string(JobStatus.CREATED.getValue()))
                .addNamedParameter("running", QueryParameterValue.string(JobStatus.RUNNING.getValue()))
                .build();

        TableResult result = runQuery(config, "getPendingJobs");
        List<PipelineJob> jobs = new ArrayList<>();
        for (FieldValueList row : result.iterateAll()) {
            jobs.add(rowToPipelineJob(row));
        }
        return jobs;
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        String sql = "SELECT entity_type, status, run_id, record_count, error_count, "
                + "started_at, completed_at FROM " + fqtn + " "
                + "WHERE system_id = @system_id AND extract_date = @extract_date";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("system_id", QueryParameterValue.string(systemId))
                .addNamedParameter("extract_date",
                        QueryParameterValue.date(extractDate.toString()))
                .build();

        TableResult result = runQuery(config, "getEntityStatus");
        List<EntityStatus> out = new ArrayList<>();
        for (FieldValueList row : result.iterateAll()) {
            String entityType = stringOrEmpty(row, "entity_type");
            String status = stringOrEmpty(row, "status");
            String runId = stringOrEmpty(row, "run_id");
            long recordCount = longOrZero(row, "record_count");
            long errorCount = longOrZero(row, "error_count");
            Optional<Instant> startedAt = instantOrEmpty(row, "started_at");
            Optional<Instant> completedAt = instantOrEmpty(row, "completed_at");
            out.add(new EntityStatus(entityType, status, runId, recordCount, errorCount,
                    startedAt, completedAt));
        }
        return out;
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        String sql = "SELECT run_id, entity_type, failure_stage, error_code, error_message, "
                + "error_file_path, completed_at AS failed_at, retry_count FROM " + fqtn + " "
                + "WHERE system_id = @system_id AND extract_date = @extract_date "
                + "AND status = @status";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("system_id", QueryParameterValue.string(systemId))
                .addNamedParameter("extract_date",
                        QueryParameterValue.date(extractDate.toString()))
                .addNamedParameter("status", QueryParameterValue.string(JobStatus.FAILED.getValue()))
                .build();

        TableResult result = runQuery(config, "getFailedJobs");
        List<FailedJob> out = new ArrayList<>();
        for (FieldValueList row : result.iterateAll()) {
            String runId = stringOrEmpty(row, "run_id");
            String entityType = stringOrEmpty(row, "entity_type");
            String failureStage = stringOrEmpty(row, "failure_stage");
            String errorCode = stringOrEmpty(row, "error_code");
            String errorMessage = stringOrEmpty(row, "error_message");
            Optional<String> errorFilePath = stringOptional(row, "error_file_path");
            Instant failedAt = instantOrEmpty(row, "failed_at").orElse(Instant.EPOCH);
            int retryCount = (int) longOrZero(row, "retry_count");
            out.add(new FailedJob(runId, entityType, failureStage, errorCode, errorMessage,
                    errorFilePath, failedAt, retryCount));
        }
        return out;
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                  String modelName) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(modelName, "modelName must not be null");

        // The Python source filters on job_type = 'FDP_TRANSFORMATION' and
        // dbt_model_name = @model_name; the Java PipelineJob doesn't carry a
        // dbt_model_name column, so we use pipeline_name as the model
        // identifier (the Java schema unifies these). job_type comes from the
        // JobType enum.
        String sql = "SELECT run_id, pipeline_name, status, record_count, "
                + "started_at, completed_at FROM " + fqtn + " "
                + "WHERE system_id = @system_id AND extract_date = @extract_date "
                + "AND job_type = @job_type AND pipeline_name = @model_name "
                + "ORDER BY created_at DESC LIMIT 1";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("system_id", QueryParameterValue.string(systemId))
                .addNamedParameter("extract_date",
                        QueryParameterValue.date(extractDate.toString()))
                .addNamedParameter("job_type",
                        QueryParameterValue.string(JobType.TRANSFORMATION.name()))
                .addNamedParameter("model_name", QueryParameterValue.string(modelName))
                .build();

        TableResult result = runQuery(config, "getFdpJobStatus");
        for (FieldValueList row : result.iterateAll()) {
            String runId = stringOrEmpty(row, "run_id");
            String pipelineName = stringOrEmpty(row, "pipeline_name");
            String status = stringOrEmpty(row, "status");
            long recordCount = longOrZero(row, "record_count");
            Optional<Instant> startedAt = instantOrEmpty(row, "started_at");
            Optional<Instant> completedAt = instantOrEmpty(row, "completed_at");
            return Optional.of(new FdpJobStatus(runId, pipelineName, status, recordCount,
                    startedAt, completedAt));
        }
        return Optional.empty();
    }

    /**
     * {@inheritDoc}
     *
     * <h2>Exactly what this deletes</h2>
     *
     * <p>One statement: {@code DELETE FROM `tableId` WHERE _run_id = @run_id}.
     * It removes the rows in the <strong>caller-supplied</strong>
     * {@code tableId} that carry this run's {@code _run_id} tag — the rows a
     * failed run partially loaded.
     *
     * <p>What it does <strong>not</strong> do:
     * <ul>
     *   <li>It does not touch the job-control ledger. The
     *       {@code pipeline_jobs} row for {@code runId} survives, with its
     *       status unchanged; clearing a run's state is
     *       {@link #markRetrying}'s job, not this method's.
     *   <li>It is not a warehouse-consistency guarantee. It is one
     *       unsynchronised DELETE: it does not fence concurrent writers, and
     *       nothing stops another process appending rows for the same
     *       {@code runId} after the DELETE commits. Call it only once the run
     *       has reached a terminal state.
     * </ul>
     *
     * @return The rows actually deleted, read from the DML statement's
     *         {@code numDmlAffectedRows} statistic. {@code TableResult}'s
     *         {@code getTotalRows()} reports a DML statement's <em>result
     *         set</em>, which is empty — so it returned 0 no matter how many
     *         rows went (issue #99).
     */
    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tableId, "tableId must not be null");

        // tableId is an arbitrary FQTN supplied by the caller — must be backtick-
        // quoted by the caller's convention. Python source wraps it in backticks
        // verbatim; mirror that.
        String sql = "DELETE FROM `" + tableId + "` WHERE _run_id = @run_id";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(runId))
                .build();

        // Deleting nothing is a legitimate outcome — a run may have failed
        // before it wrote a single row — so 0 is returned, not thrown on.
        long affected = runDml(config, "cleanupPartialLoad");
        if (affected > Integer.MAX_VALUE) {
            throw new ArithmeticException(
                    "DELETE affected rows exceed Integer.MAX_VALUE: " + affected);
        }
        return (int) affected;
    }

    /**
     * {@inheritDoc}
     *
     * <p>Not a status transition — cost metrics are attached to a job in any
     * state — so the only condition is that the row exists.
     *
     * @throws IllegalStateException if no row exists for {@code runId}.
     */
    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        Objects.requireNonNull(runId, "runId must not be null");

        String sql = "UPDATE " + fqtn + " SET estimated_cost_usd = @cost, "
                + "billed_bytes_scanned = @scanned, billed_bytes_written = @written, "
                + "updated_at = CURRENT_TIMESTAMP() "
                + "WHERE run_id = @run_id";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id", QueryParameterValue.string(runId))
                .addNamedParameter("cost", QueryParameterValue.float64(estimatedCostUsd))
                .addNamedParameter("scanned", QueryParameterValue.int64(billedBytesScanned))
                .addNamedParameter("written", QueryParameterValue.int64(billedBytesWritten))
                .build();
        if (runDml(config, "updateCostMetrics") == 0L) {
            throw new IllegalStateException(
                    "updateCostMetrics affected no rows: no job with runId=" + runId);
        }
    }

    // --- helpers -----------------------------------------------------------

    private TableResult runQuery(QueryJobConfiguration config, String op) {
        try {
            return client.query(config);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery " + op + " interrupted", e);
        }
    }

    /**
     * The states a job may legally be in immediately before a transition to
     * {@code target}. The single source of truth for the transition table in
     * this class's javadoc; every conditional write derives its {@code WHERE}
     * guard from it. Package-private so {@link RetryOrchestrator} can ask the
     * same question before it deletes anything, rather than duplicating the rule.
     *
     * @throws IllegalArgumentException if {@code target} is
     *                                  {@link JobStatus#CREATED}, which no
     *                                  transition may produce.
     */
    static Set<JobStatus> allowedPriorStates(JobStatus target) {
        switch (target) {
            case RUNNING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RETRYING);
            case SUCCEEDED:
                // Only a run that is actually running can succeed. This is the
                // guard that stops a re-run marking an already-finished job
                // succeeded a second time.
                return EnumSet.of(JobStatus.RUNNING);
            case FAILED:
                // FAILED -> FAILED is deliberate; see the class javadoc.
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING,
                        JobStatus.RETRYING, JobStatus.FAILED);
            case RETRYING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.FAILED);
            case CANCELLED:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.RETRYING);
            case CREATED:
            default:
                throw new IllegalArgumentException(
                        "CREATED is not a transition target — a job enters it via createJob; got "
                                + target);
        }
    }

    /**
     * Renders the {@code AND status IN (@prior_0, ...)} guard and collects the
     * parameters it references into {@code params}, in
     * {@link JobStatus} declaration order.
     */
    private static String priorStatePredicate(Set<JobStatus> allowed,
                                              Map<String, QueryParameterValue> params) {
        StringBuilder sb = new StringBuilder(" AND status IN (");
        int i = 0;
        for (JobStatus prior : allowed) {
            if (i > 0) {
                sb.append(", ");
            }
            String name = "prior_" + i;
            sb.append('@').append(name);
            params.put(name, QueryParameterValue.string(prior.getValue()));
            i++;
        }
        return sb.append(')').toString();
    }

    /**
     * Runs a guarded status transition and rejects it if it matched no row.
     *
     * <p>A zero affected-row count means one of two things and the caller
     * deserves to know which, so the failure path — and only the failure path —
     * pays for one extra read to tell them apart: no such run, or a run in a
     * state this transition may not leave.
     */
    private void applyTransition(QueryJobConfiguration config, String op, String runId,
                                 Set<JobStatus> allowed) {
        if (runDml(config, op) > 0L) {
            return;
        }
        Optional<PipelineJob> current = getJob(runId);
        if (current.isEmpty()) {
            throw new IllegalStateException(
                    op + " affected no rows: no job with runId=" + runId);
        }
        throw new IllegalStateException(
                op + " affected no rows: job runId=" + runId + " is "
                        + current.get().status() + ", expected one of " + allowed);
    }

    /**
     * Executes a DML statement and returns how many rows it actually changed.
     *
     * <p>Submitted as an explicit job rather than through {@code client.query}
     * because the affected-row count lives on the job's
     * {@link JobStatistics.QueryStatistics}, not on the {@link TableResult}:
     * {@code getTotalRows()} describes a result set, and a DML statement has
     * none, so it reads 0 however many rows moved (issue #99). Mirrors the
     * submit-and-wait shape already used by
     * {@code BigQueryWarehouse.waitFor} (BigQueryWarehouse.java:423-453) and
     * {@code BigQueryCostTracker.estimateDryRun} (BigQueryCostTracker.java:201-221).
     *
     * <p>A missing statistic is a hard failure, never "assume it worked" — the
     * whole point of this class's conditional writes is that an unverified
     * write is indistinguishable from a silently discarded one.
     */
    private long runDml(QueryJobConfiguration config, String op) {
        Job submitted = client.create(JobInfo.of(config));
        if (submitted == null) {
            throw new IllegalStateException(
                    "BigQuery returned a null Job for " + op + "; check ADC / quota");
        }
        Job completed;
        try {
            completed = submitted.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery " + op + " interrupted", e);
        }
        if (completed == null) {
            throw new NoSuchElementException("BigQuery job " + submitted.getJobId()
                    + " for " + op + " disappeared before completion");
        }
        if (completed.getStatus() != null && completed.getStatus().getError() != null) {
            // Synthesise a BigQueryException from the error carried on the
            // completed job's status, as BigQueryWarehouse.java:441-450 does —
            // the (int, String) ctor is the one present across the 2.x line.
            BigQueryError err = completed.getStatus().getError();
            throw new BigQueryException(500,
                    err.getMessage() != null ? err.getMessage() : err.toString());
        }
        JobStatistics.QueryStatistics stats = completed.getStatistics();
        Long affected = stats == null ? null : stats.getNumDmlAffectedRows();
        if (affected == null) {
            throw new IllegalStateException("BigQuery did not report DML affected rows for "
                    + op + "; cannot confirm the statement matched a row");
        }
        return affected;
    }

    private PipelineJob rowToPipelineJob(FieldValueList row) {
        // Build via the builder — the record has 23 fields and several
        // Optionals; positional construction would be unreadable.
        PipelineJob.Builder b = PipelineJob.builder(
                stringOrEmpty(row, "run_id"),
                stringOrEmpty(row, "system_id"),
                stringOrEmpty(row, "pipeline_name"),
                LocalDate.parse(stringOrEmpty(row, "extract_date")),
                JobStatus.valueOf(stringOrEmpty(row, "status").toUpperCase()));
        // jobType is enum.name() in createJob — parse the same way.
        String jobTypeStr = stringOrEmpty(row, "job_type");
        if (!jobTypeStr.isEmpty()) {
            b.jobType(JobType.valueOf(jobTypeStr));
        }
        b.entityType(stringOptional(row, "entity_type").orElse(null));
        b.sourceFile(stringOptional(row, "source_file").orElse(null));
        b.targetTable(stringOptional(row, "target_table").orElse(null));
        b.recordCount(longOrZero(row, "record_count"));
        b.errorCount(longOrZero(row, "error_count"));
        b.retryCount((int) longOrZero(row, "retry_count"));
        stringOptional(row, "failure_stage").ifPresent(
                v -> b.failureStage(FailureStage.valueOf(v.toUpperCase())));
        b.errorCode(stringOptional(row, "error_code").orElse(null));
        b.errorMessage(stringOptional(row, "error_message").orElse(null));
        b.errorFilePath(stringOptional(row, "error_file_path").orElse(null));
        b.estimatedCostUsd(doubleOrZero(row, "estimated_cost_usd"));
        b.billedBytesScanned(longOrZero(row, "billed_bytes_scanned"));
        b.billedBytesWritten(longOrZero(row, "billed_bytes_written"));
        instantOrEmpty(row, "created_at").ifPresent(b::createdAt);
        instantOrEmpty(row, "updated_at").ifPresent(b::updatedAt);
        instantOrEmpty(row, "started_at").ifPresent(b::startedAt);
        instantOrEmpty(row, "completed_at").ifPresent(b::completedAt);
        return b.build();
    }

    private static String stringOrEmpty(FieldValueList row, String name) {
        try {
            if (row.get(name).isNull()) {
                return "";
            }
            return row.get(name).getStringValue();
        } catch (IllegalArgumentException e) {
            // Column not in result schema.
            return "";
        }
    }

    private static Optional<String> stringOptional(FieldValueList row, String name) {
        try {
            if (row.get(name).isNull()) {
                return Optional.empty();
            }
            String v = row.get(name).getStringValue();
            return v.isEmpty() ? Optional.empty() : Optional.of(v);
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    private static long longOrZero(FieldValueList row, String name) {
        try {
            if (row.get(name).isNull()) {
                return 0L;
            }
            return row.get(name).getLongValue();
        } catch (IllegalArgumentException e) {
            return 0L;
        }
    }

    private static double doubleOrZero(FieldValueList row, String name) {
        try {
            if (row.get(name).isNull()) {
                return 0.0;
            }
            return row.get(name).getDoubleValue();
        } catch (IllegalArgumentException e) {
            return 0.0;
        }
    }

    private static Optional<Instant> instantOrEmpty(FieldValueList row, String name) {
        try {
            if (row.get(name).isNull()) {
                return Optional.empty();
            }
            // BigQuery TIMESTAMP comes back as microseconds-since-epoch.
            long micros = row.get(name).getTimestampValue();
            return Optional.of(Instant.ofEpochSecond(micros / 1_000_000L,
                    (micros % 1_000_000L) * 1_000L));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    /**
     * Convert an {@code Optional<Instant>} to a BigQuery TIMESTAMP parameter
     * value, encoded as an ISO-8601 UTC string. {@code null} when empty.
     */
    private static String toTimestampMicros(Optional<Instant> instant) {
        if (instant == null || instant.isEmpty()) {
            return null;
        }
        return instant.get().atOffset(ZoneOffset.UTC).toString();
    }
}
