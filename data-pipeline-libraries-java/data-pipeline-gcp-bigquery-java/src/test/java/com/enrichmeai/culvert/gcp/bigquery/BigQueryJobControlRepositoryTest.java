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
import com.google.cloud.bigquery.TableResult;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryJobControlRepository}. Mocks
 * {@link com.google.cloud.bigquery.BigQuery} so no real GCP credentials or
 * network are required.
 *
 * <p>Each method gets a happy-path test that captures the SQL via
 * {@link ArgumentCaptor} and verifies key SQL substrings — the SQL is the
 * contract surface that ports the Python {@code repository.py} semantics, so
 * regressions there must fail the build.
 *
 * <p>Read methods go through {@code client.query}; writes go through
 * {@code client.create(JobInfo)} + {@code Job.waitFor()}, because that is the
 * only route to {@code QueryStatistics.getNumDmlAffectedRows()} — the number
 * every conditional write is judged on. {@link #stubDml} stubs that chain.
 */
@ExtendWith(MockitoExtension.class)
class BigQueryJobControlRepositoryTest {

    private static final String PROJECT_ID = "my-project";
    private static final String DATASET = "job_control";
    private static final String TABLE = "pipeline_jobs";
    private static final String FQTN = "`my-project.job_control.pipeline_jobs`";

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
        ArgumentCaptor<JobInfo> captor = ArgumentCaptor.forClass(JobInfo.class);
        verify(client).create(captor.capture());
        QueryJobConfiguration config = captor.getValue().getConfiguration();
        return config.getQuery();
    }

    /** A one-row {@link TableResult} standing in for a job in {@code status}. */
    private void stubGetJobReturns(String status) throws InterruptedException {
        Schema schema = Schema.of(
                Field.of("run_id", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("system_id", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("pipeline_name", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("extract_date", com.google.cloud.bigquery.StandardSQLTypeName.DATE),
                Field.of("status", com.google.cloud.bigquery.StandardSQLTypeName.STRING));
        FieldValueList row = FieldValueList.of(List.of(
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "run-1"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "system-A"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "customer-ingest"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "2026-01-15"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, status)), schema.getFields());
        when(emptyResult.iterateAll()).thenReturn(List.of(row));
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
    }

    /** An empty {@link TableResult} — the run has no job-control row at all. */
    private void stubGetJobReturnsNothing() throws InterruptedException {
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
        // MERGE matched the existing row, so WHEN NOT MATCHED did not fire.
        stubDml(0L);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.createJob(sampleJob()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("run-1")
                .hasMessageContaining("already exists");
    }

    // --- getJob ------------------------------------------------------------

    @Test
    void getJobReturnsOptionalEmptyWhenNoRows() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        Optional<PipelineJob> result = repo.getJob("missing-run");

        assertThat(result).isEmpty();
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        assertThat(captor.getValue().getQuery()).contains("SELECT * FROM " + FQTN);
        assertThat(captor.getValue().getQuery()).contains("WHERE run_id = @run_id");
    }

    @Test
    void getJobMapsRowFieldsToBuilder() throws InterruptedException {
        Schema schema = Schema.of(
                Field.of("run_id", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("system_id", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("pipeline_name", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("extract_date", com.google.cloud.bigquery.StandardSQLTypeName.DATE),
                Field.of("status", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("job_type", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("entity_type", com.google.cloud.bigquery.StandardSQLTypeName.STRING),
                Field.of("retry_count", com.google.cloud.bigquery.StandardSQLTypeName.INT64));
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
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        String sql = capturedDmlSql();
        assertThat(sql).contains("UPDATE " + FQTN);
        assertThat(sql).contains("started_at = CURRENT_TIMESTAMP()");
    }

    @Test
    void updateStatusSucceededStampsCompletedAtAndRecordCount() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5_000L));

        String sql = capturedDmlSql();
        assertThat(sql).contains("completed_at = CURRENT_TIMESTAMP()");
        assertThat(sql).contains("record_count = @record_count");
    }

    /**
     * AC2: the expected prior states are in the statement, not merely checked
     * for row existence. RUNNING may only be entered from CREATED or RETRYING.
     */
    @Test
    void updateStatusGuardsOnTheExpectedPriorStates() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        ArgumentCaptor<JobInfo> captor = ArgumentCaptor.forClass(JobInfo.class);
        verify(client).create(captor.capture());
        QueryJobConfiguration config = captor.getValue().getConfiguration();
        assertThat(config.getQuery())
                .contains("WHERE run_id = @run_id AND status IN (@prior_0, @prior_1)");
        assertThat(config.getNamedParameters().get("prior_0").getValue())
                .isEqualTo(JobStatus.CREATED.getValue());
        assertThat(config.getNamedParameters().get("prior_1").getValue())
                .isEqualTo(JobStatus.RETRYING.getValue());
    }

    /** AC5: a transition from the wrong prior state is rejected, and says so. */
    @Test
    void updateStatusRejectsATransitionFromTheWrongPriorState() throws InterruptedException {
        stubDml(0L);
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("run-1")
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
    }

    /** AC5: a transition against no row at all is rejected — distinctly. */
    @Test
    void updateStatusRejectsATransitionAgainstAMissingRow() throws InterruptedException {
        stubDml(0L);
        stubGetJobReturnsNothing();
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(1L)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=run-1");
    }

    /** CREATED is not reachable by transition — a job enters it via createJob. */
    @Test
    void updateStatusRejectsCreatedAsATransitionTarget() {
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.CREATED, Optional.empty()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not a transition target");
    }

    // --- markFailed --------------------------------------------------------

    @Test
    void markFailedSetsErrorContextAndFailedStatus() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.markFailed("run-1", "E001", "schema mismatch",
                FailureStage.VALIDATION, Optional.of("gs://errors/run-1.json"));

        String sql = capturedDmlSql();
        assertThat(sql).contains("UPDATE " + FQTN);
        assertThat(sql).contains("error_code = @error_code", "error_message = @error_message",
                "failure_stage = @failure_stage", "error_file_path = @error_file_path");
        // FAILED -> FAILED is deliberate: QuarantineHandler marks a run failed,
        // then the ingestion runner's reconciliation check can mark it again.
        assertThat(sql).contains("AND status IN (@prior_0, @prior_1, @prior_2, @prior_3)");
    }

    /** AC5: a run that already SUCCEEDED cannot be re-marked failed. */
    @Test
    void markFailedRejectsARunThatAlreadySucceeded() throws InterruptedException {
        stubDml(0L);
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markFailed("run-1", "E001", "too late",
                FailureStage.VALIDATION, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
    }

    // --- markRetrying ------------------------------------------------------

    @Test
    void markRetryingUpdatesStatusAndCounter() throws InterruptedException {
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.markRetrying("run-1", 3);

        String sql = capturedDmlSql();
        assertThat(sql).contains("retry_count = @retry_count");
        assertThat(sql).contains("AND status IN (@prior_0, @prior_1, @prior_2)");
    }

    /**
     * AC5, and the point of the whole story: retrying a run that already
     * SUCCEEDED is how a re-run duplicates data. It is rejected.
     */
    @Test
    void markRetryingRejectsARunThatAlreadySucceeded() throws InterruptedException {
        stubDml(0L);
        stubGetJobReturns("succeeded");
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
    }

    @Test
    void markRetryingRejectsNegativeRetryCount() {
        BigQueryJobControlRepository repo = newRepo();
        assertThatThrownBy(() -> repo.markRetrying("run-1", -1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // --- getPendingJobs ----------------------------------------------------

    @Test
    void getPendingJobsAllSystemsSelectsCreatedAndRunning() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        List<PipelineJob> jobs = repo.getPendingJobs(Optional.empty());

        assertThat(jobs).isEmpty();
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("status IN (@created, @running)");
        assertThat(sql).doesNotContain("system_id = @system_id");
    }

    @Test
    void getPendingJobsBySystemFiltersOnSystemId() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.getPendingJobs(Optional.of("system-A"));

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        assertThat(captor.getValue().getQuery()).contains("system_id = @system_id");
    }

    // --- getEntityStatus ---------------------------------------------------

    @Test
    void getEntityStatusEmptyReturnsEmptyList() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        List<EntityStatus> result = repo.getEntityStatus("system-A", LocalDate.of(2026, 1, 15));

        assertThat(result).isEmpty();
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("entity_type", "status", "run_id");
        assertThat(sql).contains("system_id = @system_id");
        assertThat(sql).contains("extract_date = @extract_date");
    }

    // --- getFailedJobs -----------------------------------------------------

    @Test
    void getFailedJobsFiltersOnFailedStatus() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        List<FailedJob> result = repo.getFailedJobs("system-A", LocalDate.of(2026, 1, 15));

        assertThat(result).isEmpty();
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("status = @status");
        assertThat(sql).contains("failure_stage", "error_code", "error_message");
    }

    // --- getFdpJobStatus ---------------------------------------------------

    @Test
    void getFdpJobStatusEmptyReturnsOptionalEmpty() throws InterruptedException {
        when(emptyResult.iterateAll()).thenReturn(List.of());
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        Optional<FdpJobStatus> result = repo.getFdpJobStatus(
                "system-A", LocalDate.of(2026, 1, 15), "fdp_customer_v1");

        assertThat(result).isEmpty();
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("job_type = @job_type");
        assertThat(sql).contains("pipeline_name = @model_name");
        assertThat(sql).contains("ORDER BY created_at DESC LIMIT 1");
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
        stubDml(1L);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateCostMetrics("run-1", 12.34, 1_000_000L, 500_000L);

        String sql = capturedDmlSql();
        assertThat(sql).contains("estimated_cost_usd = @cost");
        assertThat(sql).contains("billed_bytes_scanned = @scanned");
        assertThat(sql).contains("billed_bytes_written = @written");
    }

    /** Not a status transition, but still conditional: the row must exist. */
    @Test
    void updateCostMetricsRejectsAMissingRow() throws InterruptedException {
        stubDml(0L);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.updateCostMetrics("run-1", 1.0, 1L, 1L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=run-1");
        // It is not a transition, so it does not pay for the disambiguating read.
        verify(client, never()).query(any(QueryJobConfiguration.class));
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
    void bigQueryExceptionOnAWritePropagates() {
        when(client.create(any(JobInfo.class)))
                .thenThrow(new BigQueryException(500, "boom"));
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(BigQueryException.class);
    }

    /**
     * An unverifiable write is the defect this story exists to remove, so a
     * missing affected-row statistic fails loudly rather than being read as
     * success.
     */
    @Test
    void missingDmlStatisticsIsAHardFailure() throws InterruptedException {
        stubDmlWithStatistics(null);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("did not report DML affected rows");
    }

    @Test
    void aNullAffectedRowCountIsAHardFailure() throws InterruptedException {
        QueryStatistics stats = mock(QueryStatistics.class);
        when(stats.getNumDmlAffectedRows()).thenReturn(null);
        stubDmlWithStatistics(stats);
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("did not report DML affected rows");
    }
}
