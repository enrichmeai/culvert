package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link RetryOrchestrator}. Stubs {@link JobControlRepository} with
 * Mockito — no real BigQuery client, no network.
 *
 * <p>Covers:
 * <ul>
 *   <li>{@code cleanupPartialLoad} is called BEFORE {@code markRetrying} (ordering)</li>
 *   <li>Correct {@code runId} and {@code tableId} forwarded to {@code cleanupPartialLoad}</li>
 *   <li>Return value carries configured row count (stub returns a specific value)</li>
 *   <li>Re-running an already-RETRYING job does NOT double-increment the counter</li>
 *   <li>No-target-table job still transitions to RETRYING (cleanup step skipped)</li>
 *   <li>{@code IllegalStateException} when run not found</li>
 * </ul>
 *
 * <p>Sprint-14 deliverable for issue
 * <a href="https://github.com/enrichmeai/culvert/issues/75">#75</a> (T14.3).
 */
@ExtendWith(MockitoExtension.class)
class RetryOrchestratorTest {

    private static final String RUN_ID = "run-abc";
    private static final String TABLE_ID = "my-project.warehouse.customers";
    private static final LocalDate EXTRACT_DATE = LocalDate.of(2026, 1, 15);

    @Mock
    private JobControlRepository repo;

    private PipelineJob failedJobWithTable(int retryCount) {
        return PipelineJob.builder(RUN_ID, "system-A", "customer-ingest", EXTRACT_DATE, JobStatus.FAILED)
                .jobType(JobType.INGESTION)
                .targetTable(TABLE_ID)
                .retryCount(retryCount)
                .build();
    }

    private PipelineJob failedJobNoTable(int retryCount) {
        return PipelineJob.builder(RUN_ID, "system-A", "customer-ingest", EXTRACT_DATE, JobStatus.FAILED)
                .jobType(JobType.INGESTION)
                .retryCount(retryCount)
                .build();
    }

    private PipelineJob retryingJob(int retryCount) {
        return PipelineJob.builder(RUN_ID, "system-A", "customer-ingest", EXTRACT_DATE, JobStatus.RETRYING)
                .jobType(JobType.INGESTION)
                .targetTable(TABLE_ID)
                .retryCount(retryCount)
                .build();
    }

    // -------------------------------------------------------------------------
    // Happy path: cleanup then markRetrying in order
    // -------------------------------------------------------------------------

    @Test
    void prepareRetry_callsCleanupBeforeMarkRetrying() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(failedJobWithTable(0)));
        when(repo.cleanupPartialLoad(RUN_ID, TABLE_ID)).thenReturn(5);

        new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        InOrder order = inOrder(repo);
        order.verify(repo).cleanupPartialLoad(RUN_ID, TABLE_ID);
        order.verify(repo).markRetrying(RUN_ID, 1);
    }

    @Test
    void prepareRetry_forwardsCorrectRunIdAndTableIdToCleanup() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(failedJobWithTable(2)));
        when(repo.cleanupPartialLoad(RUN_ID, TABLE_ID)).thenReturn(99);

        new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        verify(repo).cleanupPartialLoad(RUN_ID, TABLE_ID);
    }

    @Test
    void prepareRetry_returnsRowsCleanedFromCleanup() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(failedJobWithTable(1)));
        when(repo.cleanupPartialLoad(RUN_ID, TABLE_ID)).thenReturn(42);

        RetryOrchestrator.RetryResult result = new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        assertThat(result.rowsCleaned()).isEqualTo(42);
        assertThat(result.runId()).isEqualTo(RUN_ID);
        assertThat(result.retryCount()).isEqualTo(2); // 1 + 1
    }

    @Test
    void prepareRetry_incrementsRetryCounterByOne() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(failedJobWithTable(3)));
        when(repo.cleanupPartialLoad(RUN_ID, TABLE_ID)).thenReturn(0);

        RetryOrchestrator.RetryResult result = new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        assertThat(result.retryCount()).isEqualTo(4);
        verify(repo).markRetrying(RUN_ID, 4);
    }

    // -------------------------------------------------------------------------
    // No target table — cleanup skipped, markRetrying still called
    // -------------------------------------------------------------------------

    @Test
    void prepareRetry_noTargetTable_skipsCleanupButStillMarksRetrying() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(failedJobNoTable(0)));

        RetryOrchestrator.RetryResult result = new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        verify(repo, never()).cleanupPartialLoad(RUN_ID, TABLE_ID);
        verify(repo).markRetrying(RUN_ID, 1);
        assertThat(result.rowsCleaned()).isEqualTo(0);
    }

    // -------------------------------------------------------------------------
    // Idempotency: already RETRYING — no double-increment
    // -------------------------------------------------------------------------

    @Test
    void prepareRetry_alreadyRetrying_doesNotIncrementCounter() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(retryingJob(1)));

        RetryOrchestrator.RetryResult result = new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        // markRetrying must never be called with the next count (2)
        verify(repo, never()).markRetrying(RUN_ID, 2);
        // or any value at all
        verify(repo, never()).markRetrying(org.mockito.ArgumentMatchers.eq(RUN_ID),
                org.mockito.ArgumentMatchers.anyInt());
        assertThat(result.retryCount()).isEqualTo(1);
        assertThat(result.rowsCleaned()).isEqualTo(0);
    }

    @Test
    void prepareRetry_alreadyRetrying_doesNotCallCleanup() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.of(retryingJob(2)));

        new RetryOrchestrator(repo).prepareRetry(RUN_ID);

        verify(repo, never()).cleanupPartialLoad(org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.anyString());
    }

    // -------------------------------------------------------------------------
    // Error case: no job found
    // -------------------------------------------------------------------------

    @Test
    void prepareRetry_jobNotFound_throwsIllegalStateException() {
        when(repo.getJob(RUN_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> new RetryOrchestrator(repo).prepareRetry(RUN_ID))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(RUN_ID);
    }

    // -------------------------------------------------------------------------
    // Constructor null guard
    // -------------------------------------------------------------------------

    @Test
    void constructor_rejectsNullRepository() {
        assertThatThrownBy(() -> new RetryOrchestrator(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void prepareRetry_rejectsNullRunId() {
        assertThatThrownBy(() -> new RetryOrchestrator(repo).prepareRetry(null))
                .isInstanceOf(NullPointerException.class);
    }
}
