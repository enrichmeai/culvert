package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import software.amazon.awssdk.services.athena.AthenaClient;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.temporal.ChronoField;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * {@link JobControlRepository} implementation backed by AWS Athena (SDK v2).
 *
 * <p>This class is the artifact that settles the external review's finding #4.
 * The review argued that job control's {@code UPDATE … SET status} "blocks
 * Athena entirely", because Athena has no DML on non-Iceberg tables. Making the
 * ledger append-only (AD-2) was supposed to unblock it; AD-13 then required
 * Athena to be <em>built</em>, not merely declared unblocked. Every write below
 * is an {@code INSERT INTO}, which Athena does support on plain Hive tables —
 * so the store this class needs is one that no backend has to be able to
 * {@code UPDATE}.
 *
 * <h2>Append-only writes (AD-2)</h2>
 *
 * <p>{@code job_control.pipeline_jobs} holds one row per state change, not one
 * row per run. No statement this class builds against the ledger is an
 * {@code UPDATE} or a {@code DELETE}. Every state change —
 * {@link #updateStatus}, {@link #markFailed}, {@link #markRetrying},
 * {@link #updateCostMetrics} — reads the run's current projected state, carries
 * the whole of it forward, applies its own change, and {@code INSERT}s the
 * result as a new row stamped {@code updated_at = CAST(now() AS timestamp)}.
 *
 * <h2>Why {@link #createJob} is a plain {@code INSERT}, not a {@code MERGE}</h2>
 *
 * <p>{@link com.enrichmeai.culvert.gcp.bigquery.BigQueryJobControlRepository
 * BigQueryJobControlRepository} implements insert-if-absent as
 * {@code MERGE … WHEN NOT MATCHED THEN INSERT}, and rejects a second
 * {@code createJob} for a {@code runId} that already has a row.
 * <strong>{@code MERGE} is not available on non-Iceberg Athena</strong> (the
 * same limitation {@link AthenaWarehouse#merge} documents), and neither is a
 * unique constraint, a conditional insert, or a transaction — spine AD-6 states
 * this explicitly and sanctions the consequence. So {@code createJob} here is a
 * plain {@code INSERT INTO}, and a duplicate {@code CREATED} row is harmless:
 * the projection de-duplicates by {@code run_id}, so two {@code CREATED} rows
 * read back as one {@code CREATED} job.
 *
 * <p><strong>The honest divergence:</strong> this class therefore does
 * <em>not</em> reject a second {@code createJob} for the same {@code runId}, and
 * the BigQuery adapter does. A non-atomic read-then-insert pre-check was
 * deliberately not added — it would advertise a guarantee Athena cannot keep
 * (two racing creates both read absent and both insert) and cost a query
 * execution per create to do it.
 *
 * <h2>Reads are a projection; the first terminal state is final (AD-3)</h2>
 *
 * <p>A run has many rows, so every read ranks them and keeps one per
 * {@code run_id} — see {@link #projection}. Athena's engine v3 is Trino, so
 * {@code ROW_NUMBER() OVER (PARTITION BY … ORDER BY …)} and named CTEs are
 * available, and the ranking is the same one BigQuery uses:
 *
 * <ul>
 *   <li>a terminal row ({@code succeeded}, {@code failed}, {@code cancelled})
 *       beats a non-terminal one;
 *   <li>among terminal rows the <strong>earliest</strong> {@code updated_at}
 *       wins;
 *   <li>with no terminal row at all, the latest {@code updated_at} wins.
 * </ul>
 *
 * <p>Earliest-terminal rather than latest-row is the point, not an
 * optimisation. Under plain recency a late {@code failed} append would flip a
 * finished {@code succeeded} run to {@code failed}; {@code failed} is
 * retryable, so a retry orchestrator would then run {@code cleanupPartialLoad}
 * — {@code DELETE FROM <targetTable> WHERE _run_id} — and delete the rows the
 * successful run had just loaded. Making the first terminal state final closes
 * that data-loss path.
 *
 * <p><strong>A failed run is never resurrected in place.</strong>
 * {@code markRetrying} records the retry intent against the old run, and the
 * projection still reads {@code FAILED} because {@code failed} is terminal and
 * came first. That is not a limitation of this ranking — {@code docs/CONTRACT.md}
 * §7 and spine AD-3 rule 3 both require a retry to take a <em>new</em>
 * {@code run_id}, with the old one recorded in
 * {@code payload.previous_run_id}. A projection that let a later
 * {@code retrying} row revive a terminal run would be the same late-row-flips-a-
 * terminal-state hazard this rule exists to close, pointed the other way.
 *
 * <p>Only immutable columns — {@code run_id}, {@code system_id},
 * {@code extract_date}, {@code job_type}, {@code pipeline_name} — may be
 * filtered <em>inside</em> the projection. A {@code status} predicate must go on
 * the outer query, after {@code rn = 1}. Filtering on status first would rank a
 * partition whose winning row had already been removed, resurrecting the
 * superseded state the projection exists to hide.
 *
 * <h2>Honest limitations</h2>
 *
 * <ul>
 *   <li><strong>{@link #cleanupPartialLoad} throws
 *       {@link UnsupportedOperationException}.</strong> It is a
 *       {@code DELETE FROM <targetTable> WHERE _run_id = …}, and Athena has no
 *       {@code DELETE} on non-Iceberg tables — the same limitation
 *       {@link AthenaWarehouse#merge} and
 *       {@link AthenaWarehouse#loadFromUri}'s disposition guard document.
 *       Emulating it by rewriting the target's S3 prefix is outside what an
 *       adapter may do to a table it does not own, and would not be atomic.
 *       Refusing loudly is correct; silently deleting nothing and reporting 0
 *       would tell a retry orchestrator that a partial load had been cleaned up
 *       when it had not.
 *   <li><strong>No named parameter binding.</strong> Athena's
 *       {@code StartQueryExecution} has no equivalent of BigQuery's
 *       {@code QueryParameterValue} — see
 *       {@code AthenaWarehouse.rejectUnsupportedParams}. Every value is
 *       therefore inlined as a SQL literal, and every string goes through
 *       {@link #stringLiteral}, which escapes {@code '} by doubling it (Trino's
 *       only string escape; backslash is not special). This matters most for
 *       {@code errorMessage}, which carries arbitrary exception text.
 *   <li><strong>An append is confirmed by the query execution succeeding, not
 *       by an affected-row count.</strong> Athena's
 *       {@code QueryExecutionStatistics} carries bytes scanned but no row count
 *       (the same gap {@code AthenaWarehouse.copy} works around with a
 *       follow-up {@code COUNT(*)}), so there is no equivalent of BigQuery's
 *       {@code numDmlAffectedRows} check. A statement that reaches
 *       {@code SUCCEEDED} inserted its row; one that did not throws
 *       {@code AthenaWarehouse.AthenaQueryFailedException}.
 *   <li><strong>Read-then-append is not atomic.</strong> Two writers racing the
 *       same transition can both read the same prior state and both append.
 *       Nothing is overwritten, both rows survive, and the projection still
 *       resolves the read deterministically. That is the trade AD-2 asks for.
 *   <li><strong>{@link #updateCostMetrics} on a run that has already reached a
 *       terminal state is write-only</strong>, exactly as on BigQuery: the
 *       appended row carries the run's terminal status with a later
 *       {@code updated_at}, so the earliest terminal row still wins and the new
 *       figures never read back through this class.
 *   <li><strong>Not registered for ServiceLoader auto-config.</strong> The AWS
 *       family already registers {@code DynamoDbJobControlRepository} for
 *       {@link JobControlRepository}, and the worker rebuild takes the first
 *       constructable implementation per contract — a second AWS entry would
 *       make that non-deterministic. Athena job control is opt-in, constructed
 *       explicitly; DynamoDB stays the auto-config default.
 * </ul>
 *
 * <h2>Real-AWS validation pending</h2>
 *
 * <p><b>Flagged, not faked:</b> community LocalStack does not emulate Athena,
 * so this class ships with mocked-client unit tests only — the same standing
 * caveat {@link AthenaWarehouse} carries. In particular the exact spellings of
 * {@code INSERT INTO … (columns) VALUES (…)} and {@code CAST(now() AS timestamp)}
 * against a Glue-catalogued Hive table have not been exercised end-to-end
 * against a real Athena workgroup.
 */
public final class AthenaJobControlRepository implements JobControlRepository {

    /** The default ledger table, matching the GCP family's {@code pipeline_jobs}. */
    public static final String DEFAULT_TABLE = "pipeline_jobs";

    /**
     * The statuses a run cannot leave (AD-3). A row in one of these beats every
     * non-terminal row in the projection, and the earliest of them beats the
     * rest — so the first terminal state a run reaches is the one it keeps.
     */
    private static final Set<JobStatus> TERMINAL_STATES =
            EnumSet.of(JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED);

    /** {@code status IN ('succeeded','failed','cancelled')} — the wire values. */
    private static final String IS_TERMINAL =
            "status IN (" + literals(TERMINAL_STATES) + ")";

    /** Every ledger column, in insert order. Shared by both writers. */
    private static final String LEDGER_COLUMNS =
            "run_id, system_id, pipeline_name, extract_date, status, job_type, "
            + "entity_type, source_file, target_table, "
            + "record_count, error_count, retry_count, "
            + "failure_stage, error_code, error_message, error_file_path, "
            + "estimated_cost_usd, billed_bytes_scanned, billed_bytes_written, "
            + "created_at, updated_at, started_at, completed_at";

    /**
     * Server-side wall clock for {@code updated_at}. Trino's {@code now()} is
     * {@code timestamp(3) with time zone}; the Hive/Glue column is a plain
     * {@code timestamp}, so the cast is required rather than cosmetic.
     */
    private static final String NOW = "CAST(now() AS timestamp)";

    /** Athena renders and accepts {@code timestamp} as {@code uuuu-MM-dd HH:mm:ss.SSS}. */
    private static final DateTimeFormatter TIMESTAMP_OUT =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSS").withZone(ZoneOffset.UTC);

    /** The same shape on the way back, tolerating an absent fractional part. */
    private static final DateTimeFormatter TIMESTAMP_IN = new DateTimeFormatterBuilder()
            .appendPattern("uuuu-MM-dd HH:mm:ss")
            .appendFraction(ChronoField.NANO_OF_SECOND, 0, 9, true)
            .toFormatter(Locale.ROOT);

    private final AthenaWarehouse queries;
    private final String database;
    private final String table;
    private final String fqtn;

    /**
     * Primary constructor.
     *
     * @param client         Pre-built Athena client. Required. Not closed by
     *                       this class — the same ownership rule
     *                       {@link AthenaWarehouse} states.
     * @param database       Athena/Glue database holding the ledger table
     *                       (e.g. {@code "job_control"}). Required.
     * @param table          Ledger table (e.g. {@value #DEFAULT_TABLE}). Required.
     * @param outputLocation S3 URI ({@code s3://bucket/prefix/}) where Athena
     *                       writes query results. Required — Athena rejects
     *                       {@code StartQueryExecution} without it.
     * @throws NullPointerException if any argument is null.
     */
    public AthenaJobControlRepository(AthenaClient client, String database, String table,
                                      String outputLocation) {
        Objects.requireNonNull(client, "client must not be null");
        this.database = Objects.requireNonNull(database, "database must not be null");
        this.table = Objects.requireNonNull(table, "table must not be null");
        Objects.requireNonNull(outputLocation, "outputLocation must not be null");
        // Composed, not re-implemented: submit + poll-to-terminal + paginated
        // GetQueryResults is one code path in this module, and it is the one
        // AthenaWarehouse already documents and tests.
        this.queries = new AthenaWarehouse(client, database, outputLocation);
        this.fqtn = database + "." + table;
    }

    /**
     * {@inheritDoc}
     *
     * <p>A plain {@code INSERT INTO}: Athena has no {@code MERGE} on
     * non-Iceberg tables, so there is no insert-if-absent to run. A second
     * {@code createJob} for the same {@code runId} appends a second
     * {@code CREATED} row rather than throwing, and the projection collapses the
     * two — see the class javadoc for why that divergence from BigQuery is
     * deliberate.
     */
    @Override
    public void createJob(PipelineJob job) {
        Objects.requireNonNull(job, "job must not be null");
        append(job, NOW, timestampLiteral(job.startedAt()), timestampLiteral(job.completedAt()));
    }

    /**
     * {@inheritDoc}
     *
     * <p>The projected current state of the run: one row out of however many
     * the run has appended, chosen by {@link #projection}. A run whose first
     * terminal row is {@code succeeded} reads {@code SUCCEEDED} however many
     * later rows say otherwise.
     */
    @Override
    public Optional<PipelineJob> getJob(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");
        List<Map<String, Object>> rows = read(
                projection("run_id = " + stringLiteral(runId)) + "SELECT * FROM ranked WHERE rn = 1");
        return rows.isEmpty() ? Optional.empty() : Optional.of(toPipelineJob(rows.get(0)));
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends the run's next state. The projected current state is read
     * first and a prior state this transition may not leave is rejected before
     * anything is written, so a transition that would change nothing still does
     * not report success — the guard that the removed compare-and-set DML used
     * to carry.
     *
     * @throws IllegalArgumentException if {@code status} is
     *                                  {@link JobStatus#CREATED}.
     * @throws IllegalStateException    if the run has no row at all, or its
     *                                  projected status is not an allowed prior
     *                                  state for {@code status}.
     */
    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(totalRecords, "totalRecords must not be null");

        Set<JobStatus> allowed = allowedPriorStates(status);
        PipelineJob current = requireTransitionFrom("updateStatus", runId, allowed);

        PipelineJob.Builder next = carryForward(current, status);
        if (status == JobStatus.SUCCEEDED) {
            next.recordCount(totalRecords.orElse(0L));
        }
        appendTransition(next.build(), status == JobStatus.RUNNING, status == JobStatus.SUCCEEDED);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends a {@code failed} row. The projected prior state must be one of
     * {@code CREATED}, {@code RUNNING}, {@code RETRYING} or {@code FAILED} — a
     * run that already {@code SUCCEEDED} cannot be re-marked failed, and under
     * AD-3 could not read as failed even if a row were appended behind this
     * method's back.
     *
     * @throws IllegalStateException if the run has no row at all, or its
     *                               projected status is not an allowed prior state.
     */
    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(errorCode, "errorCode must not be null");
        Objects.requireNonNull(errorMessage, "errorMessage must not be null");
        Objects.requireNonNull(failureStage, "failureStage must not be null");
        Objects.requireNonNull(errorFilePath, "errorFilePath must not be null");

        PipelineJob current = requireTransitionFrom(
                "markFailed", runId, allowedPriorStates(JobStatus.FAILED));

        PipelineJob next = carryForward(current, JobStatus.FAILED)
                .errorCode(errorCode)
                .errorMessage(errorMessage)
                .failureStage(failureStage)
                .errorFilePath(errorFilePath.orElse(null))
                .build();
        appendTransition(next, false, true);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends a {@code retrying} row recording the retry intent. The
     * projected prior state must be one of {@code CREATED}, {@code RUNNING} or
     * {@code FAILED}; retrying a run that already {@code SUCCEEDED} is exactly
     * how a re-run duplicates data, so it is rejected.
     *
     * <p><strong>This does not move a failed run out of {@code FAILED}.</strong>
     * The {@code failed} row is terminal and came first, so it keeps winning the
     * projection. Per {@code docs/CONTRACT.md} §7 the retry itself is a new run
     * with a new {@code run_id} — see the class javadoc.
     *
     * @throws IllegalStateException if the run has no row at all, or its
     *                               projected status is not an allowed prior state.
     */
    @Override
    public void markRetrying(String runId, int retryCount) {
        Objects.requireNonNull(runId, "runId must not be null");
        if (retryCount < 0) {
            throw new IllegalArgumentException("retryCount must be >= 0, got " + retryCount);
        }
        PipelineJob current = requireTransitionFrom(
                "markRetrying", runId, allowedPriorStates(JobStatus.RETRYING));

        appendTransition(carryForward(current, JobStatus.RETRYING).retryCount(retryCount).build(),
                false, false);
    }

    /**
     * {@inheritDoc}
     *
     * <p>The status filter sits on the projection, never inside it: a run that
     * has since succeeded still has its old {@code running} row in the ledger,
     * and ranking a partition pre-filtered on status would hand that row back
     * as pending.
     */
    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId must not be null");

        String inner = systemId.map(id -> "system_id = " + stringLiteral(id)).orElse("");
        String sql = projection(inner)
                + "SELECT * FROM ranked WHERE rn = 1 AND status IN ("
                + literals(EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING))
                + ") ORDER BY created_at";

        List<PipelineJob> jobs = new ArrayList<>();
        for (Map<String, Object> row : read(sql)) {
            jobs.add(toPipelineJob(row));
        }
        return jobs;
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        String sql = projection(systemAndDate(systemId, extractDate))
                + "SELECT * FROM ranked WHERE rn = 1";

        List<EntityStatus> out = new ArrayList<>();
        for (Map<String, Object> row : read(sql)) {
            out.add(new EntityStatus(
                    stringOrEmpty(row, "entity_type"),
                    stringOrEmpty(row, "status"),
                    stringOrEmpty(row, "run_id"),
                    longOrZero(row, "record_count"),
                    longOrZero(row, "error_count"),
                    instantOrEmpty(row, "started_at"),
                    instantOrEmpty(row, "completed_at")));
        }
        return out;
    }

    /**
     * {@inheritDoc}
     *
     * <p>{@code status = 'failed'} is applied AFTER {@code rn = 1}. Inside the
     * projection it would rank a partition stripped of its winning row, so a run
     * whose first terminal state was {@code succeeded} would come back failed —
     * and a failed job is a retryable job, which deletes data.
     */
    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        String sql = projection(systemAndDate(systemId, extractDate))
                + "SELECT * FROM ranked WHERE rn = 1 AND status = "
                + stringLiteral(JobStatus.FAILED.getValue());

        List<FailedJob> out = new ArrayList<>();
        for (Map<String, Object> row : read(sql)) {
            out.add(new FailedJob(
                    stringOrEmpty(row, "run_id"),
                    stringOrEmpty(row, "entity_type"),
                    stringOrEmpty(row, "failure_stage"),
                    stringOrEmpty(row, "error_code"),
                    stringOrEmpty(row, "error_message"),
                    stringOptional(row, "error_file_path"),
                    instantOrEmpty(row, "completed_at").orElse(Instant.EPOCH),
                    (int) longOrZero(row, "retry_count")));
        }
        return out;
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                  String modelName) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(modelName, "modelName must not be null");

        // The Java PipelineJob carries no dbt_model_name column, so
        // pipeline_name is the model identifier — mirrors
        // BigQueryJobControlRepository.getFdpJobStatus.
        String sql = projection(systemAndDate(systemId, extractDate)
                + " AND job_type = " + stringLiteral(JobType.TRANSFORMATION.name())
                + " AND pipeline_name = " + stringLiteral(modelName))
                + "SELECT * FROM ranked WHERE rn = 1 ORDER BY created_at DESC LIMIT 1";

        for (Map<String, Object> row : read(sql)) {
            return Optional.of(new FdpJobStatus(
                    stringOrEmpty(row, "run_id"),
                    stringOrEmpty(row, "pipeline_name"),
                    stringOrEmpty(row, "status"),
                    longOrZero(row, "record_count"),
                    instantOrEmpty(row, "started_at"),
                    instantOrEmpty(row, "completed_at")));
        }
        return Optional.empty();
    }

    /**
     * {@inheritDoc}
     *
     * <p><strong>Not supported on Athena.</strong> This method is a
     * {@code DELETE FROM <tableId> WHERE _run_id = …} against the
     * caller-supplied warehouse table, and Athena has no {@code DELETE} outside
     * Iceberg-backed tables — the same limitation {@link AthenaWarehouse#merge}
     * documents. Note this is not an AD-2 concern: AD-2 binds
     * {@code job_control.*}, and this statement never touched the ledger. It is
     * simply a capability Athena does not have.
     *
     * @throws UnsupportedOperationException always.
     */
    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tableId, "tableId must not be null");
        throw new UnsupportedOperationException(
                "cleanupPartialLoad() is not supported by AthenaJobControlRepository: it is a "
                        + "DELETE against the caller-supplied target table, and Athena has no DML "
                        + "on non-Iceberg tables (same limitation as AthenaWarehouse.merge). "
                        + "Reporting 0 rows cleaned would tell a retry orchestrator a partial load "
                        + "had been removed when it had not. Use an Iceberg-backed target table and "
                        + "AthenaWarehouse.execute(String, Map) with an explicit DELETE, or drop and "
                        + "reload the run's S3 partition outside Culvert. "
                        + "Tracked at https://github.com/enrichmeai/culvert/issues/149");
    }

    /**
     * {@inheritDoc}
     *
     * <p>Not a status transition — cost metrics are attached to a job in any
     * state — so the only condition is that the run exists. The appended row
     * carries the projected status forward unchanged.
     *
     * <p><strong>Write-only on a finished run.</strong> If the run has already
     * reached a terminal state, the appended row is terminal too and carries a
     * later {@code updated_at}, so AD-3's earliest-terminal rule keeps the
     * original row winning and these figures never read back through this class.
     *
     * @throws IllegalStateException if the run has no row at all.
     */
    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        Objects.requireNonNull(runId, "runId must not be null");

        PipelineJob current = getJob(runId).orElseThrow(() -> new IllegalStateException(
                "updateCostMetrics rejected: no job with runId=" + runId));

        appendTransition(carryForward(current, current.status())
                .estimatedCostUsd(estimatedCostUsd)
                .billedBytesScanned(billedBytesScanned)
                .billedBytesWritten(billedBytesWritten)
                .build(), false, false);
    }

    // --- the projection ----------------------------------------------------

    /**
     * The latest-state projection over the append-only ledger (AD-3), leaving
     * the caller to keep {@code rn = 1}. Every read in this class is built on
     * this and none may re-implement it — recency logic of its own is exactly
     * what AD-3 forbids.
     *
     * @param immutableFilter A predicate pushed inside the projection, or
     *                        {@code ""}. <strong>Only columns a state change
     *                        carries forward unchanged</strong> may appear here:
     *                        {@code run_id}, {@code system_id},
     *                        {@code extract_date}, {@code job_type},
     *                        {@code pipeline_name}. Such a predicate removes
     *                        whole partitions and cannot change which row wins
     *                        inside one. A {@code status} predicate would, so it
     *                        belongs on the outer query beside {@code rn = 1}.
     */
    private String projection(String immutableFilter) {
        return "WITH ranked AS (SELECT *, ROW_NUMBER() OVER ("
                + "PARTITION BY run_id ORDER BY "
                + "CASE WHEN " + IS_TERMINAL + " THEN 0 ELSE 1 END, "
                + "CASE WHEN " + IS_TERMINAL + " THEN updated_at END ASC, "
                + "updated_at DESC) AS rn FROM " + fqtn
                + (immutableFilter.isEmpty() ? "" : " WHERE " + immutableFilter)
                + ") ";
    }

    /**
     * The states a job may legally be in immediately before a transition to
     * {@code target}. Mirrors {@code BigQueryJobControlRepository.allowedPriorStates}
     * (BigQueryJobControlRepository.java:648-671) exactly — the transition table
     * is a contract-level rule, not a per-backend one.
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
                return EnumSet.of(JobStatus.RUNNING);
            case FAILED:
                // FAILED -> FAILED is deliberate: a quarantine handler and a
                // reconciliation check can both fail the same run. Both rows
                // survive; under AD-3 the FIRST failure is the one that reads
                // back.
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
     * Reads the run's projected state and rejects a transition it may not make.
     *
     * <p>An append cannot fail on a guard the way the compare-and-set DML it
     * replaced did, so the guard moves ahead of the write.
     */
    private PipelineJob requireTransitionFrom(String op, String runId, Set<JobStatus> allowed) {
        PipelineJob current = getJob(runId).orElseThrow(() -> new IllegalStateException(
                op + " rejected: no job with runId=" + runId));
        if (!allowed.contains(current.status())) {
            throw new IllegalStateException(op + " rejected: job runId=" + runId + " is "
                    + current.status() + ", expected one of " + allowed);
        }
        return current;
    }

    /**
     * Copies every field of the projected state onto a builder, under a new
     * status. {@code updated_at} is deliberately not carried — the appended row
     * gets a fresh one, and it is the ordering key the projection ranks on.
     */
    private static PipelineJob.Builder carryForward(PipelineJob current, JobStatus status) {
        return PipelineJob.builder(current.runId(), current.systemId(),
                        current.pipelineName(), current.extractDate(), status)
                .jobType(current.jobType())
                .entityType(current.entityType().orElse(null))
                .sourceFile(current.sourceFile().orElse(null))
                .targetTable(current.targetTable().orElse(null))
                .recordCount(current.recordCount())
                .errorCount(current.errorCount())
                .retryCount(current.retryCount())
                .failureStage(current.failureStage().orElse(null))
                .errorCode(current.errorCode().orElse(null))
                .errorMessage(current.errorMessage().orElse(null))
                .errorFilePath(current.errorFilePath().orElse(null))
                .estimatedCostUsd(current.estimatedCostUsd())
                .billedBytesScanned(current.billedBytesScanned())
                .billedBytesWritten(current.billedBytesWritten())
                .createdAt(current.createdAt())
                .startedAt(current.startedAt().orElse(null))
                .completedAt(current.completedAt().orElse(null));
    }

    /**
     * Appends one full-state row for a state change, carrying {@code created_at}
     * forward as a literal and stamping the two lifecycle timestamps that the
     * transition owns.
     *
     * @param stampStartedNow   Stamp {@code started_at} server-side rather than
     *                          carrying the projected value forward — a
     *                          {@code RUNNING} transition.
     * @param stampCompletedNow The same for {@code completed_at} — a
     *                          {@code SUCCEEDED} or {@code FAILED} transition.
     */
    private void appendTransition(PipelineJob job, boolean stampStartedNow,
                                  boolean stampCompletedNow) {
        append(job,
                timestampLiteral(Optional.of(job.createdAt())),
                stampStartedNow ? NOW : timestampLiteral(job.startedAt()),
                stampCompletedNow ? NOW : timestampLiteral(job.completedAt()));
    }

    /**
     * The single write path: one {@code INSERT INTO} carrying every ledger
     * column. Never an {@code UPDATE}, never a {@code DELETE} — the run's
     * earlier rows are left exactly as they are (AD-2).
     */
    private void append(PipelineJob job, String createdAt, String startedAt, String completedAt) {
        String sql = "INSERT INTO " + fqtn + " (" + LEDGER_COLUMNS + ") VALUES ("
                + String.join(", ",
                        stringLiteral(job.runId()),
                        stringLiteral(job.systemId()),
                        stringLiteral(job.pipelineName()),
                        dateLiteral(job.extractDate()),
                        stringLiteral(job.status().getValue()),
                        stringLiteral(job.jobType().name()),
                        stringLiteral(job.entityType().orElse(null)),
                        stringLiteral(job.sourceFile().orElse(null)),
                        stringLiteral(job.targetTable().orElse(null)),
                        Long.toString(job.recordCount()),
                        Long.toString(job.errorCount()),
                        Integer.toString(job.retryCount()),
                        stringLiteral(job.failureStage().map(FailureStage::getValue).orElse(null)),
                        stringLiteral(job.errorCode().orElse(null)),
                        stringLiteral(job.errorMessage().orElse(null)),
                        stringLiteral(job.errorFilePath().orElse(null)),
                        Double.toString(job.estimatedCostUsd()),
                        Long.toString(job.billedBytesScanned()),
                        Long.toString(job.billedBytesWritten()),
                        createdAt, NOW, startedAt, completedAt)
                + ")";
        queries.execute(sql, Map.of());
    }

    private List<Map<String, Object>> read(String sql) {
        List<Map<String, Object>> rows = new ArrayList<>();
        Iterator<Map<String, Object>> iterator = queries.query(sql, Map.of());
        while (iterator.hasNext()) {
            rows.add(iterator.next());
        }
        return rows;
    }

    // --- SQL literals ------------------------------------------------------

    /**
     * A Trino string literal, or {@code NULL}. The single quote is doubled,
     * which is Trino's only string escape — backslash carries no meaning inside
     * a {@code '…'} literal, so nothing else needs escaping. Every
     * caller-supplied string in this class goes through here, because Athena
     * offers no parameter binding to do it for us.
     */
    private static String stringLiteral(String value) {
        return value == null ? "NULL" : "'" + value.replace("'", "''") + "'";
    }

    private static String dateLiteral(LocalDate value) {
        return value == null ? "NULL" : "DATE '" + value + "'";
    }

    private static String timestampLiteral(Optional<Instant> value) {
        return value == null || value.isEmpty()
                ? "NULL"
                : "TIMESTAMP '" + TIMESTAMP_OUT.format(value.get()) + "'";
    }

    /** The wire values of {@code statuses} as a comma-separated literal list. */
    private static String literals(Set<JobStatus> statuses) {
        StringBuilder sb = new StringBuilder();
        for (JobStatus status : statuses) {
            if (sb.length() > 0) {
                sb.append(',');
            }
            sb.append('\'').append(status.getValue()).append('\'');
        }
        return sb.toString();
    }

    private static String systemAndDate(String systemId, LocalDate extractDate) {
        return "system_id = " + stringLiteral(systemId)
                + " AND extract_date = " + dateLiteral(extractDate);
    }

    // --- row mapping -------------------------------------------------------

    private static PipelineJob toPipelineJob(Map<String, Object> row) {
        PipelineJob.Builder b = PipelineJob.builder(
                stringOrEmpty(row, "run_id"),
                stringOrEmpty(row, "system_id"),
                stringOrEmpty(row, "pipeline_name"),
                LocalDate.parse(stringOrEmpty(row, "extract_date")),
                JobStatus.valueOf(stringOrEmpty(row, "status").toUpperCase(Locale.ROOT)));

        String jobType = stringOrEmpty(row, "job_type");
        if (!jobType.isEmpty()) {
            b.jobType(JobType.valueOf(jobType.toUpperCase(Locale.ROOT)));
        }
        b.entityType(stringOptional(row, "entity_type").orElse(null));
        b.sourceFile(stringOptional(row, "source_file").orElse(null));
        b.targetTable(stringOptional(row, "target_table").orElse(null));
        b.recordCount(longOrZero(row, "record_count"));
        b.errorCount(longOrZero(row, "error_count"));
        b.retryCount((int) longOrZero(row, "retry_count"));
        stringOptional(row, "failure_stage").ifPresent(
                v -> b.failureStage(FailureStage.valueOf(v.toUpperCase(Locale.ROOT))));
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

    /** Athena hands every column back as a string (or null) via {@code varCharValue}. */
    private static String stringOrEmpty(Map<String, Object> row, String name) {
        Object value = row.get(name);
        return value == null ? "" : value.toString();
    }

    private static Optional<String> stringOptional(Map<String, Object> row, String name) {
        String value = stringOrEmpty(row, name);
        return value.isEmpty() ? Optional.empty() : Optional.of(value);
    }

    private static long longOrZero(Map<String, Object> row, String name) {
        String value = stringOrEmpty(row, name);
        return value.isEmpty() ? 0L : Long.parseLong(value.trim());
    }

    private static double doubleOrZero(Map<String, Object> row, String name) {
        String value = stringOrEmpty(row, name);
        return value.isEmpty() ? 0.0 : Double.parseDouble(value.trim());
    }

    private static Optional<Instant> instantOrEmpty(Map<String, Object> row, String name) {
        String value = stringOrEmpty(row, name);
        if (value.isEmpty()) {
            return Optional.empty();
        }
        // Athena renders a `timestamp` with no zone; the ledger is written in
        // UTC (TIMESTAMP_OUT), so it is read back in UTC.
        return Optional.of(LocalDateTime.parse(value.trim(), TIMESTAMP_IN).toInstant(ZoneOffset.UTC));
    }
}
