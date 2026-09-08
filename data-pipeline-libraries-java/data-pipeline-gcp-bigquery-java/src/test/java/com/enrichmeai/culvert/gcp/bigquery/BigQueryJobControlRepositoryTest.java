package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldValue;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics.QueryStatistics;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.Schema;
import com.google.cloud.bigquery.StandardSQLTypeName;
import com.google.cloud.bigquery.TableResult;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryJobControlRepository}. Mocks
 * {@link com.google.cloud.bigquery.BigQuery} so no real GCP credentials or
 * network are required.
 *
 * <p>These tests are about the <strong>SQL shape</strong> — that the ledger is
 * only ever appended to, that every read carries the same projection, and that
 * no status predicate leaks inside that projection. They cannot prove the
 * projection <em>ranks</em> correctly, because a mocked client never executes
 * it; {@link BigQueryJobControlProjectionTest} does that against a fake that
 * really ranks the rows it holds, per AD-12.
 *
 * <p>Reads go through {@code client.query}; writes go through
 * {@code client.create(JobInfo)} + {@code Job.waitFor()}, because that is the
 * only route to {@code QueryStatistics.getNumDmlAffectedRows()} — the number
 * every write is judged on. {@link #stubDml} stubs that chain.
 *
 * <p>A write now reads before it appends (the transition guard moved out of the
 * DML when the {@code UPDATE} went), so a write test stubs both.
 */
@ExtendWith(MockitoExtension.class)
class BigQueryJobControlRepositoryTest {

    private static final String PROJECT_ID = "my-project";
    private static final String DATASET = "job_control";
    private static final String TABLE = "pipeline_jobs";
    private static final String FQTN = "`my-project.job_control.pipeline_jobs`";

    /** The exact ranking the projection must carry, per AD-3. */
    private static final String PROJECTION =
            "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY "
            + "CASE WHEN status IN ('succeeded','failed','cancelled') THEN 0 ELSE 1 END, "
            + "CASE WHEN status IN ('succeeded','failed','cancelled') THEN updated_at END ASC, "
            + "updated_at DESC) AS rn FROM " + FQTN;

    @Mock
    private BigQuery client;

    @Mock
    private TableResult emptyResult;

    private BigQueryJobControlRepository newRepo() {
        return new BigQueryJobControlRepository(client, PROJECT_ID, DATASET, TABLE);
    }

    /** Stub create → waitFor → statistics so a DML statement reports {@code affected} rows. */
    private void stubDml(long affected) throws InterruptedException {
        QueryStatistics stats = mock(QueryStatistics.class);
        when(stats.getNumDmlAffectedRows()).thenReturn(affected);
        stubDmlWithStatistics(stats);
    }

    /** As {@link #stubDml} but with caller-chosen (possibly null) statistics. */
    private void stubDmlWithStatistics(QueryStatistics stats) throws InterruptedException {
        Job submitted = mock(Job.class);
        Job completed = mock(Job.class);
        when(submitted.waitFor()).thenReturn(completed);
        when(completed.getStatistics()).thenReturn(stats);
        when(client.create(any(JobInfo.class))).thenReturn(submitted);
    }

    /** The SQL of the single DML statement submitted via {@code client.create}. */
    private String capturedDmlSql() {
        return capturedDmlConfig().getQuery();
    }

    /** The single DML statement submitted via {@code client.create}. */
    private QueryJobConfiguration capturedDmlConfig() {
        ArgumentCaptor<JobInfo> captor = ArgumentCaptor.forClass(JobInfo.class);
        verify(client).create(captor.capture());
        return captor.getValue().getConfiguration();
    }

    /** The SQL of the single read submitted via {@code client.query}. */
    private String capturedQuerySql() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        return captor.getValue().getQuery();
    }

    /** A one-row {@link TableResult} standing in for a job in {@code status}. */
    private void stubGetJobReturns(String status) throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of(jobRow(status)));
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
    }

    private static FieldValueList jobRow(String status) {
        Schema schema = Schema.of(
                Field.of("run_id", StandardSQLTypeName.STRING),
                Field.of("system_id", StandardSQLTypeName.STRING),
                Field.of("pipeline_name", StandardSQLTypeName.STRING),
                Field.of("extract_date", StandardSQLTypeName.DATE),
                Field.of("status", StandardSQLTypeName.STRING));
        return FieldValueList.of(List.of(
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "run-1"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "system-A"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "customer-ingest"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "2026-01-15"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, status)), schema.getFields());
    }

    /** An empty {@link TableResult} — the projection matched no row. */
    private void stubReadReturnsNothing() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
    }

    private PipelineJob sampleJob() {
        return PipelineJob.builder(
                        "run-1", "system-A", "customer-ingest",
                        LocalDate.of(2026, 1, 15), JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customer")
                .sourceFile("gs://bucket/customers.csv")
                .build();
    }

    // --- AD-2: the ledger is append-only -----------------------------------

    /**
     * AD-2, the acceptance criterion this class exists to satisfy: no statement
     * built against the job-control ledger is an {@code UPDATE} or a
     * {@code DELETE}. Every write and every read is exercised and every
     * statement captured, so a re-mutating regression anywhere fails here.
     */
    @Test
    void noLedgerStatementIsAnUpdateOrADelete() throws InterruptedException {
        AtomicReference<String> projected = new AtomicReference<>("created");
        when(client.query(any(QueryJobConfiguration.class))).thenAnswer(invocation -> {
            TableResult result = mock(TableResult.class);
            when(result.iterateAll()).thenReturn(List.of(jobRow(projected.get())));
            return result;
        });
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();
        LocalDate date = LocalDate.of(2026, 1, 15);

        repo.createJob(sampleJob());
        projected.set("created");
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        projected.set("running");
        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(10L));
        projected.set("running");
        repo.markFailed("run-1", "E001", "boom", FailureStage.VALIDATION, Optional.empty());
        projected.set("failed");
        repo.markRetrying("run-1", 1);
        projected.set("running");
        repo.updateCostMetrics("run-1", 1.0, 2L, 3L);
        repo.getJob("run-1");
        repo.getPendingJobs(Optional.of("system-A"));
        repo.getPendingJobs(Optional.empty());
        repo.getEntityStatus("system-A", date);
        repo.getFailedJobs("system-A", date);
        repo.getFdpJobStatus("system-A", date, "fdp_customer_v1");

        for (String sql : allLedgerSql()) {
            assertThat(sql)
                    .as("ledger statement must be append-only: %s", sql)
                    .doesNotContain("UPDATE")
                    .doesNotContain("DELETE")
                    .doesNotContain("TRUNCATE")
                    .doesNotContain("WHEN MATCHED");
        }
        // Sanity: the scan really saw every statement — 6 writes (createJob plus
        // five appends) and 11 reads (6 read calls plus the projected read each
        // of the five state changes makes before it appends).
        assertThat(allLedgerSql()).hasSize(17);
    }

    /** Every SQL statement the repository submitted, writes and reads alike. */
    private List<String> allLedgerSql() throws InterruptedException {
        List<String> sql = new ArrayList<>();
        ArgumentCaptor<JobInfo> writes = ArgumentCaptor.forClass(JobInfo.class);
        verify(client, atLeastOnce()).create(writes.capture());
        for (JobInfo info : writes.getAllValues()) {
            sql.add(((QueryJobConfiguration) info.getConfiguration()).getQuery());
        }
        ArgumentCaptor<QueryJobConfiguration> reads =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client, atLeastOnce()).query(reads.capture());
        for (QueryJobConfiguration config : reads.getAllValues()) {
            sql.add(config.getQuery());
        }
        return sql;
    }

    /**
     * The class's one DELETE is scoped to the caller's warehouse table. AD-2
     * binds {@code job_control.*}, and AD-3's whole purpose is to keep a
     * succeeded run away from this statement rather than to remove it.
     */
    @Test
    void theOnlyDeleteTargetsTheCallersTableAndNeverTheLedger() throws InterruptedException {
        stubDml(3L);
        BigQueryJobControlRepository repo = newRepo();

        repo.cleanupPartialLoad("run-1", "my-project.warehouse.customers");

        String sql = capturedDmlSql();
        assertThat(sql).startsWith("DELETE FROM `my-project.warehouse.customers`");
        assertThat(sql).doesNotContain(FQTN);
        assertThat(sql).doesNotContain(DATASET);
        assertThat(sql).doesNotContain(TABLE);
    }

    // --- AD-3: every read carries the same projection -----------------------

    @Test
    void everyReadRanksTheLedgerWithTheSameProjection() throws InterruptedException {
        LocalDate date = LocalDate.of(2026, 1, 15);
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        repo.getJob("run-1");
        repo.getPendingJobs(Optional.empty());
        repo.getPendingJobs(Optional.of("system-A"));
        repo.getEntityStatus("system-A", date);
        repo.getFailedJobs("system-A", date);
        repo.getFdpJobStatus("system-A", date, "fdp_customer_v1");

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client, atLeastOnce()).query(captor.capture());
        assertThat(captor.getAllValues()).hasSize(6);
        for (QueryJobConfiguration config : captor.getAllValues()) {
            assertThat(config.getQuery())
                    .as("read must project through the ranking CTE: %s", config.getQuery())
                    .startsWith(PROJECTION)
                    .contains("WHERE rn = 1");
        }
    }

    /**
     * The status filter belongs on the projection, never inside it. Ranking a
     * partition pre-filtered on status hands back a row the projection had
     * already superseded — a succeeded run reading as failed, and a failed run
     * is one {@code RetryOrchestrator} will delete data for.
     */
    @Test
    void noReadFiltersOnStatusInsideTheProjection() throws InterruptedException {
        LocalDate date = LocalDate.of(2026, 1, 15);
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        repo.getJob("run-1");
        repo.getPendingJobs(Optional.of("system-A"));
        repo.getEntityStatus("system-A", date);
        repo.getFailedJobs("system-A", date);
        repo.getFdpJobStatus("system-A", date, "fdp_customer_v1");

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client, atLeastOnce()).query(captor.capture());
        for (QueryJobConfiguration config : captor.getAllValues()) {
            String sql = config.getQuery();
            // Everything up to the CTE's closing paren, i.e. what gets ranked.
            String cte = sql.substring(0, sql.indexOf(") SELECT") + 1);
            assertThat(cte)
                    .as("no status predicate may sit inside the CTE: %s", cte)
                    .doesNotContain("@status")
                    .doesNotContain("@created")
                    .doesNotContain("@running");
        }
    }

    // --- createJob ---------------------------------------------------------

    @Test
    void createJobMergesInsertIfAbsentWithAllColumns() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.createJob(sampleJob());

        String sql = capturedDmlSql();
        assertThat(sql).contains("MERGE INTO " + FQTN);
        assertThat(sql).contains("ON T.run_id = S.run_id");
        assertThat(sql).contains("WHEN NOT MATCHED THEN INSERT");
        assertThat(sql).contains("run_id", "system_id", "pipeline_name",
                "extract_date", "status", "job_type");
        assertThat(sql).contains("CURRENT_TIMESTAMP()");
    }

    /** AC1: createJob is insert-if-absent and fails if the runId already exists. */
    @Test
    void createJobRejectsARunIdThatAlreadyExists() throws InterruptedException {
        // MERGE matched an existing row for the run, so WHEN NOT MATCHED did not fire.
        stubDml(0L);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.createJob(sampleJob()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("run-1")
                .hasMessageContaining("already exists");
    }

    /**
     * A present {@code startedAt} / {@code completedAt} binds. It did not
     * before: {@code toTimestampMicros} handed an ISO-8601 string to
     * {@code QueryParameterValue.timestamp(String)}, which accepts only
     * {@code "yyyy-MM-dd HH:mm:ss.SSSSSSZZ"} and threw. Nothing exercised it
     * while both were usually absent; an append binds {@code created_at},
     * which never is.
     */
    @Test
    void timestampColumnsBindAsMicrosecondsNotAnIsoString() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();
        Instant startedAt = Instant.parse("2026-01-15T09:30:00.123456Z");

        repo.createJob(PipelineJob.builder("run-1", "system-A", "customer-ingest",
                        LocalDate.of(2026, 1, 15), JobStatus.CREATED)
                .startedAt(startedAt)
                .build());

        assertThat(capturedDmlConfig().getNamedParameters().get("started_at").getValue())
                .isEqualTo("2026-01-15 09:30:00.123456+00:00");
    }

    // --- getJob ------------------------------------------------------------

    @Test
    void getJobReturnsOptionalEmptyWhenNoRows() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        Optional<PipelineJob> result = repo.getJob("missing-run");

        assertThat(result).isEmpty();
        String sql = capturedQuerySql();
        assertThat(sql).startsWith(PROJECTION);
        assertThat(sql).contains(" WHERE run_id = @run_id) ");
        assertThat(sql).endsWith("SELECT * FROM ranked WHERE rn = 1");
    }

    @Test
    void getJobMapsRowFieldsToBuilder() throws InterruptedException {
        Schema schema = Schema.of(
                Field.of("run_id", StandardSQLTypeName.STRING),
                Field.of("system_id", StandardSQLTypeName.STRING),
                Field.of("pipeline_name", StandardSQLTypeName.STRING),
                Field.of("extract_date", StandardSQLTypeName.DATE),
                Field.of("status", StandardSQLTypeName.STRING),
                Field.of("job_type", StandardSQLTypeName.STRING),
                Field.of("entity_type", StandardSQLTypeName.STRING),
                Field.of("retry_count", StandardSQLTypeName.INT64));
        FieldValueList row = FieldValueList.of(List.of(
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "run-1"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "system-A"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "customer-ingest"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "2026-01-15"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "running"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "INGESTION"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "customer"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "2")), schema.getFields());
        when(emptyResult.iterateAll()).thenReturn(List.of(row));
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        Optional<PipelineJob> result = repo.getJob("run-1");

        assertThat(result).isPresent();
        PipelineJob job = result.get();
        assertThat(job.runId()).isEqualTo("run-1");
        assertThat(job.systemId()).isEqualTo("system-A");
        assertThat(job.pipelineName()).isEqualTo("customer-ingest");
        assertThat(job.status()).isEqualTo(JobStatus.RUNNING);
        assertThat(job.jobType()).isEqualTo(JobType.INGESTION);
        assertThat(job.entityType()).contains("customer");
        assertThat(job.retryCount()).isEqualTo(2);
    }

    // --- updateStatus ------------------------------------------------------

    @Test
    void updateStatusRunningStampsStartedAt() throws InterruptedException {
        stubGetJobReturns("created");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        String sql = capturedDmlSql();
        assertThat(sql).startsWith("INSERT INTO " + FQTN);
        // created_at is carried, updated_at and started_at are stamped now,
        // completed_at is carried — the order is LEDGER_COLUMNS' last four.
        assertThat(sql).endsWith(
                "@created_at, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), @completed_at)");
    }

    @Test
    void updateStatusSucceededStampsCompletedAtAndRecordCount() throws InterruptedException {
        stubGetJobReturns("running");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5_000L));

        QueryJobConfiguration config = capturedDmlConfig();
        assertThat(config.getQuery()).endsWith(
                "@created_at, CURRENT_TIMESTAMP(), @started_at, CURRENT_TIMESTAMP())");
        assertThat(config.getNamedParameters().get("record_count").getValue())
                .isEqualTo("5000");
        assertThat(config.getNamedParameters().get("status").getValue())
                .isEqualTo(JobStatus.SUCCEEDED.getValue());
    }

    /**
     * The appended row carries the whole of the projected state, not just the
     * columns the transition touches — a partial row would read back as a
     * blanked-out job the moment it won the projection.
     */
    @Test
    void updateStatusAppendsAFullStateRowCarryingTheProjectedState()
            throws InterruptedException {
        stubGetJobReturns("created");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        QueryJobConfiguration config = capturedDmlConfig();
        assertThat(config.getQuery()).contains(
                "(run_id, system_id, pipeline_name, extract_date, status, job_type, "
                + "entity_type, source_file, target_table, "
                + "record_count, error_count, retry_count, "
                + "failure_stage, error_code, error_message, error_file_path, "
                + "estimated_cost_usd, billed_bytes_scanned, billed_bytes_written, "
                + "created_at, updated_at, started_at, completed_at)");
        // Carried forward from the row the projection returned.
        assertThat(config.getNamedParameters().get("run_id").getValue()).isEqualTo("run-1");
        assertThat(config.getNamedParameters().get("system_id").getValue())
                .isEqualTo("system-A");
        assertThat(config.getNamedParameters().get("pipeline_name").getValue())
                .isEqualTo("customer-ingest");
        assertThat(config.getNamedParameters().get("extract_date").getValue())
                .isEqualTo("2026-01-15");
    }

    /** AC5: a transition from the wrong prior state is rejected, and says so. */
    @Test
    void updateStatusRejectsATransitionFromTheWrongPriorState() throws InterruptedException {
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("run-1")
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
        // Rejected before the append: nothing reached the ledger.
        verify(client, never()).create(any(JobInfo.class));
    }

    /** AC5: a transition against no row at all is rejected — distinctly. */
    @Test
    void updateStatusRejectsATransitionAgainstAMissingRow() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(1L)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=run-1");
        verify(client, never()).create(any(JobInfo.class));
    }

    /** CREATED is not reachable by transition — a job enters it via createJob. */
    @Test
    void updateStatusRejectsCreatedAsATransitionTarget() throws InterruptedException {
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.CREATED, Optional.empty()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not a transition target");
        // Rejected without paying for the projected read.
        verify(client, never()).query(any(QueryJobConfiguration.class));
    }

    // --- markFailed --------------------------------------------------------

    @Test
    void markFailedSetsErrorContextAndFailedStatus() throws InterruptedException {
        stubGetJobReturns("running");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.markFailed("run-1", "E001", "schema mismatch",
                FailureStage.VALIDATION, Optional.of("gs://errors/run-1.json"));

        QueryJobConfiguration config = capturedDmlConfig();
        assertThat(config.getQuery()).startsWith("INSERT INTO " + FQTN);
        assertThat(config.getQuery()).endsWith(
                "@created_at, CURRENT_TIMESTAMP(), @started_at, CURRENT_TIMESTAMP())");
        assertThat(config.getNamedParameters().get("status").getValue())
                .isEqualTo(JobStatus.FAILED.getValue());
        assertThat(config.getNamedParameters().get("error_code").getValue()).isEqualTo("E001");
        assertThat(config.getNamedParameters().get("error_message").getValue())
                .isEqualTo("schema mismatch");
        assertThat(config.getNamedParameters().get("failure_stage").getValue())
                .isEqualTo(FailureStage.VALIDATION.getValue());
        assertThat(config.getNamedParameters().get("error_file_path").getValue())
                .isEqualTo("gs://errors/run-1.json");
    }

    /** AC5: a run that already SUCCEEDED cannot be re-marked failed. */
    @Test
    void markFailedRejectsARunThatAlreadySucceeded() throws InterruptedException {
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markFailed("run-1", "E001", "too late",
                FailureStage.VALIDATION, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
        verify(client, never()).create(any(JobInfo.class));
    }

    // --- markRetrying ------------------------------------------------------

    @Test
    void markRetryingUpdatesStatusAndCounter() throws InterruptedException {
        stubGetJobReturns("failed");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.markRetrying("run-1", 3);

        QueryJobConfiguration config = capturedDmlConfig();
        assertThat(config.getQuery()).startsWith("INSERT INTO " + FQTN);
        assertThat(config.getNamedParameters().get("retry_count").getValue()).isEqualTo("3");
        assertThat(config.getNamedParameters().get("status").getValue())
                .isEqualTo(JobStatus.RETRYING.getValue());
    }

    /**
     * AC5, and the point of the whole story: retrying a run that already
     * SUCCEEDED is how a re-run duplicates data. It is rejected.
     */
    @Test
    void markRetryingRejectsARunThatAlreadySucceeded() throws InterruptedException {
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
        verify(client, never()).create(any(JobInfo.class));
    }

    @Test
    void markRetryingRejectsNegativeRetryCount() throws InterruptedException {
        BigQueryJobControlRepository repo = newRepo();
        assertThatThrownBy(() -> repo.markRetrying("run-1", -1))
                .isInstanceOf(IllegalArgumentException.class);
        verify(client, never()).query(any(QueryJobConfiguration.class));
    }

    // --- getPendingJobs ----------------------------------------------------

    @Test
    void getPendingJobsAllSystemsSelectsCreatedAndRunning() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        List<PipelineJob> jobs = repo.getPendingJobs(Optional.empty());

        assertThat(jobs).isEmpty();
        String sql = capturedQuerySql();
        assertThat(sql).contains("WHERE rn = 1 AND status IN (@created, @running)");
        assertThat(sql).doesNotContain("system_id = @system_id");
        // No filter at all inside the CTE when no system is named.
        assertThat(sql).contains(") AS rn FROM " + FQTN + ") SELECT");
    }

    @Test
    void getPendingJobsBySystemFiltersOnSystemId() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        repo.getPendingJobs(Optional.of("system-A"));

        String sql = capturedQuerySql();
        // system_id is immutable across a run's rows, so it may narrow the CTE.
        assertThat(sql).contains(") AS rn FROM " + FQTN + " WHERE system_id = @system_id) ");
        assertThat(sql).contains("WHERE rn = 1 AND status IN (@created, @running)");
    }

    // --- getEntityStatus ---------------------------------------------------

    @Test
    void getEntityStatusEmptyReturnsEmptyList() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        List<EntityStatus> result = repo.getEntityStatus("system-A", LocalDate.of(2026, 1, 15));

        assertThat(result).isEmpty();
        String sql = capturedQuerySql();
        assertThat(sql).contains("entity_type", "status", "run_id");
        assertThat(sql).contains("system_id = @system_id");
        assertThat(sql).contains("extract_date = @extract_date");
        assertThat(sql).contains("FROM ranked WHERE rn = 1");
    }

    // --- getFailedJobs -----------------------------------------------------

    @Test
    void getFailedJobsFiltersOnFailedStatus() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        List<FailedJob> result = repo.getFailedJobs("system-A", LocalDate.of(2026, 1, 15));

        assertThat(result).isEmpty();
        String sql = capturedQuerySql();
        assertThat(sql).contains("WHERE rn = 1 AND status = @status");
        assertThat(sql).contains("failure_stage", "error_code", "error_message");
    }

    // --- getFdpJobStatus ---------------------------------------------------

    @Test
    void getFdpJobStatusEmptyReturnsOptionalEmpty() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        Optional<FdpJobStatus> result = repo.getFdpJobStatus(
                "system-A", LocalDate.of(2026, 1, 15), "fdp_customer_v1");

        assertThat(result).isEmpty();
        String sql = capturedQuerySql();
        assertThat(sql).contains("job_type = @job_type");
        assertThat(sql).contains("pipeline_name = @model_name");
        // The one-row cut is applied to the projection, not to the raw ledger.
        assertThat(sql).endsWith("FROM ranked WHERE rn = 1 ORDER BY created_at DESC LIMIT 1");
    }

    // --- cleanupPartialLoad ------------------------------------------------

    /**
     * AC3 / issue #99: the count comes from the DML statement's
     * {@code numDmlAffectedRows}, not from {@code TableResult.getTotalRows()},
     * which describes a result set a DELETE does not have.
     */
    @Test
    void cleanupPartialLoadReturnsTheRowsTheDeleteActuallyRemoved() throws InterruptedException {
        stubDml(42L);
        BigQueryJobControlRepository repo = newRepo();

        int deleted = repo.cleanupPartialLoad("run-1", "my-project.warehouse.customers");

        assertThat(deleted).isEqualTo(42);
        String sql = capturedDmlSql();
        assertThat(sql).contains("DELETE FROM `my-project.warehouse.customers`");
        assertThat(sql).contains("WHERE _run_id = @run_id");
    }

    /** Deleting nothing is a legitimate outcome, not a failure. */
    @Test
    void cleanupPartialLoadReturnsZeroWhenNothingWasPartiallyLoaded()
            throws InterruptedException {
        stubDml(0L);
        BigQueryJobControlRepository repo = newRepo();

        assertThat(repo.cleanupPartialLoad("run-1", "my-project.warehouse.customers"))
                .isZero();
    }

    // --- updateCostMetrics -------------------------------------------------

    @Test
    void updateCostMetricsSetsAllThreeFinOpsFields() throws InterruptedException {
        stubGetJobReturns("running");
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateCostMetrics("run-1", 12.34, 1_000_000L, 500_000L);

        QueryJobConfiguration config = capturedDmlConfig();
        assertThat(config.getQuery()).startsWith("INSERT INTO " + FQTN);
        assertThat(config.getNamedParameters().get("estimated_cost_usd").getValue())
                .isEqualTo("12.34");
        assertThat(config.getNamedParameters().get("billed_bytes_scanned").getValue())
                .isEqualTo("1000000");
        assertThat(config.getNamedParameters().get("billed_bytes_written").getValue())
                .isEqualTo("500000");
        // Not a transition: the projected status is carried forward unchanged.
        assertThat(config.getNamedParameters().get("status").getValue())
                .isEqualTo(JobStatus.RUNNING.getValue());
    }

    /** Not a status transition, but still conditional: the run must exist. */
    @Test
    void updateCostMetricsRejectsAMissingRow() throws InterruptedException {
        stubReadReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateCostMetrics("run-1", 1.0, 1L, 1L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=run-1");
        verify(client, never()).create(any(JobInfo.class));
    }

    // --- error path --------------------------------------------------------

    /** Read path (client.query): interruption is rewrapped, flag restored. */
    @Test
    void interruptedExceptionOnAReadIsRewrappedAndInterruptFlagRestored()
            throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class)))
                .thenThrow(new InterruptedException("test"));
        BigQueryJobControlRepository repo = newRepo();

        try {
            assertThatThrownBy(() -> repo.getJob("run-1"))
                    .isInstanceOf(RuntimeException.class)
                    .hasMessageContaining("interrupted");
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            // Clear the interrupted flag so we don't poison other tests.
            Thread.interrupted();
        }
    }

    /** Write path (Job.waitFor): same guarantee. */
    @Test
    void interruptedExceptionOnAWriteIsRewrappedAndInterruptFlagRestored()
            throws InterruptedException {
        stubGetJobReturns("failed");
        Job submitted = mock(Job.class);
        when(submitted.waitFor()).thenThrow(new InterruptedException("test"));
        when(client.create(any(JobInfo.class))).thenReturn(submitted);
        BigQueryJobControlRepository repo = newRepo();

        try {
            assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                    .isInstanceOf(RuntimeException.class)
                    .hasMessageContaining("interrupted");
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void bigQueryExceptionOnAReadPropagates() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class)))
                .thenThrow(new BigQueryException(500, "boom"));
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.getJob("run-1"))
                .isInstanceOf(BigQueryException.class);
    }

    @Test
    void bigQueryExceptionOnAWritePropagates() throws InterruptedException {
        stubGetJobReturns("failed");
        when(client.create(any(JobInfo.class)))
                .thenThrow(new BigQueryException(500, "boom"));
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(BigQueryException.class);
    }

    /**
     * An unverifiable write is the defect story 1.3 removed, so a missing
     * affected-row statistic fails loudly rather than being read as success.
     */
    @Test
    void missingDmlStatisticsIsAHardFailure() throws InterruptedException {
        stubGetJobReturns("failed");
        stubDmlWithStatistics(null);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("did not report DML affected rows");
    }

    @Test
    void aNullAffectedRowCountIsAHardFailure() throws InterruptedException {
        stubGetJobReturns("failed");
        QueryStatistics stats = mock(QueryStatistics.class);
        when(stats.getNumDmlAffectedRows()).thenReturn(null);
        stubDmlWithStatistics(stats);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("did not report DML affected rows");
    }

    /** An append that the ledger reports as changing nothing is a hard failure. */
    @Test
    void anAppendThatMovedNoRowIsAHardFailure() throws InterruptedException {
        stubGetJobReturns("failed");
        stubDml(0L);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("appended no row for runId=run-1");
    }
}
