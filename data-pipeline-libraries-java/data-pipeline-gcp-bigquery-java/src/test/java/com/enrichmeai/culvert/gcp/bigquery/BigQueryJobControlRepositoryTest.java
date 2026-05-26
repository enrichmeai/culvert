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
    void createJobIssuesInsertWithAllColumns() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.createJob(sampleJob());

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("INSERT INTO " + FQTN);
        assertThat(sql).contains("run_id", "system_id", "pipeline_name",
                "extract_date", "status", "job_type");
        assertThat(sql).contains("CURRENT_TIMESTAMP()");
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
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("UPDATE " + FQTN);
        assertThat(sql).contains("started_at = CURRENT_TIMESTAMP()");
    }

    @Test
    void updateStatusSucceededStampsCompletedAtAndRecordCount() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5_000L));

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("completed_at = CURRENT_TIMESTAMP()");
        assertThat(sql).contains("record_count = @record_count");
    }

    // --- markFailed --------------------------------------------------------

    @Test
    void markFailedSetsErrorContextAndFailedStatus() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.markFailed("run-1", "E001", "schema mismatch",
                FailureStage.VALIDATION, Optional.of("gs://errors/run-1.json"));

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("UPDATE " + FQTN);
        assertThat(sql).contains("error_code = @error_code", "error_message = @error_message",
                "failure_stage = @failure_stage", "error_file_path = @error_file_path");
    }

    // --- markRetrying ------------------------------------------------------

    @Test
    void markRetryingUpdatesStatusAndCounter() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.markRetrying("run-1", 3);

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("retry_count = @retry_count");
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

    @Test
    void cleanupPartialLoadDeletesByRunId() throws InterruptedException {
        when(emptyResult.getTotalRows()).thenReturn(42L);
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        int deleted = repo.cleanupPartialLoad("run-1", "my-project.warehouse.customers");

        assertThat(deleted).isEqualTo(42);
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("DELETE FROM `my-project.warehouse.customers`");
        assertThat(sql).contains("WHERE _run_id = @run_id");
    }

    // --- updateCostMetrics -------------------------------------------------

    @Test
    void updateCostMetricsSetsAllThreeFinOpsFields() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(emptyResult);
        BigQueryJobControlRepository repo = newRepo();

        repo.updateCostMetrics("run-1", 12.34, 1_000_000L, 500_000L);

        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(captor.capture());
        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("estimated_cost_usd = @cost");
        assertThat(sql).contains("billed_bytes_scanned = @scanned");
        assertThat(sql).contains("billed_bytes_written = @written");
    }

    // --- error path --------------------------------------------------------

    @Test
    void interruptedExceptionIsRewrappedAndInterruptFlagRestored() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class)))
                .thenThrow(new InterruptedException("test"));
        BigQueryJobControlRepository repo = newRepo();

        try {
            assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                    .isInstanceOf(RuntimeException.class)
                    .hasMessageContaining("interrupted");
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            // Clear the interrupted flag so we don't poison other tests.
            Thread.interrupted();
        }
    }

    @Test
    void bigQueryExceptionPropagates() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class)))
                .thenThrow(new BigQueryException(500, "boom"));
        BigQueryJobControlRepository repo = newRepo();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(BigQueryException.class);
    }
}
