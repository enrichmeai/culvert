package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * AD-12's behavioural suite: the append-only guarantees, asserted through
 * behaviour rather than through the text of the SQL.
 *
 * <p>{@link BigQueryJobControlRepositoryTest} pins the SQL's shape, but a
 * mocked client returns whatever it was told to return no matter what the query
 * says — so a shape test cannot tell a correct projection from a broken one.
 * {@link InMemoryBigQueryLedger} closes that hole: it holds the rows the
 * repository appends and <strong>reads the ranking out of the submitted
 * SQL</strong>, parsing the {@code ORDER BY} key list of the CTE into a
 * comparator (see {@link InMemoryBigQueryLedger#comparatorFrom}). Change the
 * ordering in {@code BigQueryJobControlRepository.rankedCte} and these tests
 * change verdict — which is the only way "the earliest terminal state wins" can
 * be tested at unit level at all.
 *
 * <p>The same fixture backs {@link BigQueryJobControlContractTest}, so the
 * guarantees below and the cross-cloud contract are asserted against one
 * ranking implementation rather than two.
 */
class BigQueryJobControlProjectionTest {

    private static final String PROJECT = "my-project";
    private static final String DATASET = "job_control";
    private static final String TABLE = "pipeline_jobs";

    private InMemoryBigQueryLedger ledger;
    private BigQueryJobControlRepository repo;

    @BeforeEach
    void setUp() throws InterruptedException {
        ledger = new InMemoryBigQueryLedger();
        repo = new BigQueryJobControlRepository(ledger.client(), PROJECT, DATASET, TABLE);
    }

    private PipelineJob newJob() {
        return PipelineJob.builder("run-1", "system-A", "customer-ingest",
                        LocalDate.of(2026, 1, 15), JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customer")
                .targetTable("my-project.warehouse.customers")
                .build();
    }

    /** Drives a run as far as {@code SUCCEEDED} through the repository itself. */
    private void runToSuccess() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(1_000L));
    }

    // --- AD-12, guarantee 1: failure-then-success reads FAILED --------------

    /**
     * A run that failed and then had a success row land after it reads
     * {@code FAILED}. Nothing was overwritten to achieve that — both rows are
     * in the ledger and the projection picks the earlier terminal one.
     */
    @Test
    void appendFailureThenSuccessReadsFailed() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("run-1", "E001", "reconciliation mismatch",
                FailureStage.VALIDATION, Optional.empty());
        // A success event landing after the failure: the control-flow defect
        // the external review found (a runner reporting success after already
        // having marked the run failed). It cannot go through updateStatus,
        // which rejects it — so it is appended the way a stray writer would.
        ledger.appendRaw("run-1", JobStatus.SUCCEEDED);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
        assertThat(ledger.rowsFor("run-1")).hasSize(4);
    }

    // --- AD-12, guarantee 2: the data-loss guard ---------------------------

    /**
     * The guard the whole design exists for. A succeeded run with a LATE
     * failure row still reads {@code SUCCEEDED}, so it is not retryable, so
     * {@link RetryOrchestrator} never reaches {@code cleanupPartialLoad} — the
     * {@code DELETE FROM <targetTable> WHERE _run_id} that would erase the rows
     * the successful run had just loaded.
     *
     * <p>This test fails if terminal precedence is removed: under plain
     * recency the late {@code failed} row wins, {@code FAILED} is retryable,
     * and the delete goes through.
     */
    @Test
    void appendSuccessThenLateFailureReadsSucceededAndIsNotRetryable() {
        runToSuccess();
        ledger.appendRaw("run-1", JobStatus.FAILED);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.SUCCEEDED);

        assertThatThrownBy(() -> new RetryOrchestrator(repo).prepareRetry("run-1"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("Nothing was deleted.");
        assertThat(ledger.deletes()).isEmpty();
    }

    /** The same guarantee, one layer down: the ledger itself is never mutated. */
    @Test
    void everyStateChangeAddsARowAndRemovesNone() {
        runToSuccess();
        repo.updateCostMetrics("run-1", 4.25, 100L, 200L);

        assertThat(ledger.rowsFor("run-1")).hasSize(4);
        assertThat(ledger.statusHistory("run-1"))
                .containsExactly("created", "running", "succeeded", "succeeded");
        assertThat(ledger.deletes()).isEmpty();
        assertThat(ledger.updates()).isEmpty();
    }

    // --- AD-12, guarantee 3: illegal transitions still throw ---------------

    @Test
    void aTransitionOutOfATerminalStateIsStillRejected() {
        runToSuccess();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
        assertThatThrownBy(() -> repo.markFailed("run-1", "E001", "too late",
                FailureStage.LOAD, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected one of");

        // Three rejections, and not one of them reached the ledger.
        assertThat(ledger.rowsFor("run-1")).hasSize(3);
    }

    @Test
    void createJobRefusesASecondHistoryForTheSameRun() {
        repo.createJob(newJob());

        assertThatThrownBy(() -> repo.createJob(newJob()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("already exists");
        assertThat(ledger.rowsFor("run-1")).hasSize(1);
    }

    // --- the projection's other two rules ----------------------------------

    /** With no terminal row, the projection falls back to the latest row. */
    @Test
    void beforeTerminalTheLatestRowWins() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("run-1", "E001", "first", FailureStage.VALIDATION, Optional.empty());
        // `failed` is terminal, so back the run out and check the pre-terminal
        // rule on a separate run instead.
        repo.createJob(PipelineJob.builder("run-2", "system-A", "customer-ingest",
                LocalDate.of(2026, 1, 15), JobStatus.CREATED).build());
        repo.updateStatus("run-2", JobStatus.RUNNING, Optional.empty());
        repo.markRetrying("run-2", 1);

        assertThat(repo.getJob("run-2")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.RETRYING);
        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
    }

    /**
     * The consequence of AD-3 rule 1 that deserves to be deliberate rather than
     * discovered: cost metrics recorded after a run has finished are appended
     * to the ledger but never win the projection, so they do not read back
     * through this class. Documented on
     * {@code BigQueryJobControlRepository.updateCostMetrics}.
     */
    @Test
    void costMetricsRecordedAfterATerminalStateAreWriteOnly() {
        runToSuccess();

        repo.updateCostMetrics("run-1", 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(0.0);
        // The row is in the ledger; it just is not the projected one.
        assertThat(ledger.rowsFor("run-1")).hasSize(4);
        assertThat(ledger.rowsFor("run-1").get(3).get("estimated_cost_usd")).isEqualTo("99.99");
    }

    /** Recorded before the run finishes, the same call reads back. */
    @Test
    void costMetricsRecordedBeforeTheRunFinishesReadBack() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        repo.updateCostMetrics("run-1", 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(99.99);
    }
}
