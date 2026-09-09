package com.enrichmeai.culvert.aws.athena;

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
 * AD-12's behavioural suite for the Athena adapter, and the reason
 * {@link AthenaJobControlContractTest} alone is not enough.
 *
 * <p>The shared contract suite drives every state change through the repository,
 * so its late-failure cases are stopped by the pre-write transition guard and
 * never reach the ranking at all — remove terminal precedence from
 * {@code AthenaJobControlRepository.projection} and that suite still passes.
 * The tests here append the contradicting row the way a stray writer would
 * ({@link InMemoryAthenaLedger#appendRaw}), which is the only way the
 * projection's own behaviour gets asserted.
 *
 * <p>Mirrors {@code BigQueryJobControlProjectionTest} in the GCP family, so the
 * two backends are held to one set of guarantees rather than two.
 */
class AthenaJobControlProjectionTest {

    private static final String DATABASE = "job_control";
    private static final String TABLE = "pipeline_jobs";
    private static final String OUTPUT_LOCATION = "s3://contract-bucket/athena-results/";
    private static final String RUN = "run-1";

    private InMemoryAthenaLedger ledger;
    private AthenaJobControlRepository repo;

    @BeforeEach
    void setUp() {
        ledger = new InMemoryAthenaLedger();
        repo = new AthenaJobControlRepository(ledger.client(), DATABASE, TABLE, OUTPUT_LOCATION);
    }

    private PipelineJob newJob() {
        return PipelineJob.builder(RUN, "system-A", "customer-ingest",
                        LocalDate.of(2026, 1, 15), JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customer")
                .targetTable("warehouse.customers")
                .build();
    }

    private void runToSuccess() {
        repo.createJob(newJob());
        repo.updateStatus(RUN, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(RUN, JobStatus.SUCCEEDED, Optional.of(1_000L));
    }

    /**
     * A run that failed and then had a success row land after it reads
     * {@code FAILED}. Nothing was overwritten to achieve that — both rows are in
     * the ledger and the projection picks the earlier terminal one.
     */
    @Test
    void appendFailureThenSuccessReadsFailed() {
        repo.createJob(newJob());
        repo.updateStatus(RUN, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(RUN, "E001", "reconciliation mismatch",
                FailureStage.VALIDATION, Optional.empty());
        // A success event landing after the failure. It cannot go through
        // updateStatus, which rejects it — so it is appended as a stray writer
        // would append it.
        ledger.appendRaw(RUN, JobStatus.SUCCEEDED);

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
        assertThat(ledger.rowsFor(RUN)).hasSize(4);
    }

    /**
     * THE DATA-LOSS GUARD, asserted against the ranking rather than the write
     * guard. A succeeded run with a LATE failure row still reads
     * {@code SUCCEEDED}, so it is not retryable, so a retry orchestrator never
     * reaches {@code cleanupPartialLoad}. This test fails if terminal precedence
     * is removed from the projection: under plain recency the late {@code failed}
     * row wins.
     */
    @Test
    void appendSuccessThenLateFailureStillReadsSucceeded() {
        runToSuccess();
        ledger.appendRaw(RUN, JobStatus.FAILED);

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(ledger.rowsFor(RUN)).hasSize(4);
    }

    /**
     * The same guarantee for the list projection: a succeeded run with a late
     * {@code running} row appended must not reappear as pending work.
     */
    @Test
    void aLateRunningRowDoesNotResurrectAFinishedRunAsPending() {
        runToSuccess();
        ledger.appendRaw(RUN, JobStatus.RUNNING);

        assertThat(repo.getPendingJobs(Optional.of("system-A")))
                .noneMatch(job -> job.runId().equals(RUN));
    }

    /**
     * A stray {@code retrying} row does not revive a terminal run either —
     * {@code docs/CONTRACT.md} §7: the retry is a new {@code run_id}.
     */
    @Test
    void aStrayRetryingRowDoesNotReviveATerminalRun() {
        repo.createJob(newJob());
        repo.updateStatus(RUN, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(RUN, "E001", "failed", FailureStage.LOAD, Optional.empty());
        ledger.appendRaw(RUN, JobStatus.RETRYING);

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
    }

    /** AD-2, one layer down: the ledger is only ever appended to. */
    @Test
    void everyStateChangeAddsARowAndRemovesNone() {
        runToSuccess();
        repo.updateCostMetrics(RUN, 4.25, 100L, 200L);

        assertThat(ledger.rowsFor(RUN)).hasSize(4);
        assertThat(ledger.statusHistory(RUN))
                .containsExactly("created", "running", "succeeded", "succeeded");
        assertThat(ledger.deletes()).isEmpty();
        assertThat(ledger.updates()).isEmpty();
    }

    @Test
    void aTransitionOutOfATerminalStateIsStillRejected() {
        runToSuccess();

        assertThatThrownBy(() -> repo.markRetrying(RUN, 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
        assertThatThrownBy(() -> repo.markFailed(RUN, "E001", "too late",
                FailureStage.LOAD, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");

        // Two rejections, and neither reached the ledger.
        assertThat(ledger.rowsFor(RUN)).hasSize(3);
    }

    /**
     * Cost metrics recorded after a run has finished are appended but never win
     * the projection — the deliberate consequence of AD-3 rule 1, documented on
     * {@code AthenaJobControlRepository.updateCostMetrics}.
     */
    @Test
    void costMetricsRecordedAfterATerminalStateAreWriteOnly() {
        runToSuccess();

        repo.updateCostMetrics(RUN, 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(0.0);
        assertThat(ledger.rowsFor(RUN).get(3).get("estimated_cost_usd")).isEqualTo("99.99");
    }

    /** Recorded before the run finishes, the same call reads back. */
    @Test
    void costMetricsRecordedBeforeTheRunFinishesReadBack() {
        repo.createJob(newJob());
        repo.updateStatus(RUN, JobStatus.RUNNING, Optional.empty());

        repo.updateCostMetrics(RUN, 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(99.99);
    }

    // --- the Athena-specific limitations, asserted rather than asserted-about -

    /**
     * {@code MERGE} is unavailable on non-Iceberg Athena, so {@code createJob} is
     * a plain {@code INSERT INTO} and cannot reject a duplicate. The projection
     * de-duplicates by {@code run_id}, which is why that is harmless — both rows
     * are in the ledger and the run still reads as one CREATED job.
     */
    @Test
    void aDuplicateCreateAppendsASecondRowAndStillReadsAsOneCreatedJob() {
        repo.createJob(newJob());
        repo.createJob(newJob());

        assertThat(ledger.rowsFor(RUN)).hasSize(2);
        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.CREATED);
    }

    /** Athena has no DELETE on non-Iceberg tables: refuse loudly, never fake it. */
    @Test
    void cleanupPartialLoadRefusesRatherThanReportingNothingDeleted() {
        assertThatThrownBy(() -> repo.cleanupPartialLoad(RUN, "warehouse.customers"))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("no DML on non-Iceberg tables")
                .hasMessageContaining("issues/149");
        assertThat(ledger.deletes()).isEmpty();
    }

    /**
     * Athena offers no parameter binding, so every value is inlined — which
     * makes literal escaping load-bearing. An error message carrying a quote
     * must round-trip, not truncate the statement.
     */
    @Test
    void aQuoteInAnErrorMessageIsEscapedAndRoundTrips() {
        repo.createJob(newJob());
        repo.updateStatus(RUN, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(RUN, "E'01", "row 7's value didn't parse",
                FailureStage.VALIDATION, Optional.empty());

        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::errorMessage)
                .isEqualTo(Optional.of("row 7's value didn't parse"));
        assertThat(repo.getJob(RUN)).get()
                .extracting(PipelineJob::errorCode).isEqualTo(Optional.of("E'01"));
    }
}
