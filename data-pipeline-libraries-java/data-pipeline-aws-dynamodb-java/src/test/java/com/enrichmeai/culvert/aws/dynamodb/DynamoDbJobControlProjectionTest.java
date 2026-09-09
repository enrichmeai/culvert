package com.enrichmeai.culvert.aws.dynamodb;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The append-only guarantees (AD-2/AD-3), asserted where the shared contract
 * test structurally cannot reach.
 *
 * <p>{@code JobControlRepositoryContractTest} drives everything through the
 * repository, so its late-failure case is intercepted by the transition guard
 * before an item is ever written — which means the contract suite alone would
 * stay green even if the projection degenerated to last-write-wins. That is not
 * a hypothetical hole: read-then-append is deliberately not atomic (see the
 * class javadoc), so a racing writer, a replayed event or a second process can
 * land a contradicting item that no guard saw.
 *
 * <p>These tests therefore write such items <strong>straight into the
 * ledger</strong> via {@link InMemoryDynamoDb#inject}, at an explicitly later
 * {@code event_seq}, and then ask the repository what the run's state is. Break
 * the terminal-precedence rule in
 * {@code DynamoDbJobControlRepository.project} and
 * {@link #aLateFailureLandingInTheLedgerCannotUnseatASucceededRun} goes red —
 * which is the only way "the earliest terminal state wins" can be tested at
 * unit level at all. Mirrors {@code BigQueryJobControlProjectionTest}'s role in
 * the GCP module.
 */
class DynamoDbJobControlProjectionTest {

    private static final String TABLE = "job_control";
    private static final String RUN_ID = "run-1";
    private static final LocalDate EXTRACT_DATE = LocalDate.of(2026, 1, 15);

    /**
     * Sorts after every generated {@code event_seq} (which are zero-padded
     * epoch nanoseconds, so they start with a 0 for the next two centuries).
     * Written out rather than taken from the clock: a microsecond tie with the
     * item it is meant to follow would make these tests coin flips.
     */
    private static final String LATE_EVENT_SEQ = "99999999999999999999-late";

    private InMemoryDynamoDb client;
    private DynamoDbJobControlRepository repo;

    @BeforeEach
    void setUp() {
        client = new InMemoryDynamoDb();
        repo = new DynamoDbJobControlRepository(client, TABLE);
    }

    private static PipelineJob newJob(String runId) {
        return PipelineJob.builder(runId, "system-A", "customer-ingest",
                        EXTRACT_DATE, JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customer")
                .targetTable("warehouse.customers")
                .build();
    }

    private void runToSuccess() {
        repo.createJob(newJob(RUN_ID));
        repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(RUN_ID, JobStatus.SUCCEEDED, Optional.of(3L));
    }

    /**
     * Lands an item the repository never wrote: the run's latest state with a
     * different status, at a sort key past every generated one. This is what a
     * writer that raced the guard, or a redelivered event, leaves behind. Same
     * hook the shared contract suite calls {@code appendRaw}.
     */
    private void injectLate(String runId, JobStatus status, String errorCode) {
        client.appendRaw(TABLE, runId, status.getValue(), errorCode);
    }

    // --- AD-3: the data-loss guard -----------------------------------------

    @Test
    void aLateFailureLandingInTheLedgerCannotUnseatASucceededRun() {
        // THE DATA-LOSS GUARD. A succeeded run that reads back FAILED is a
        // retryable run, and RetryOrchestrator.prepareRetry calls
        // cleanupPartialLoad, which deletes the rows this run just loaded.
        runToSuccess();

        injectLate(RUN_ID, JobStatus.FAILED, "LATE_ERROR");

        assertThat(repo.getJob(RUN_ID)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(repo.getJob(RUN_ID).orElseThrow().errorCode())
                .as("the contradicting item's detail must not leak into the projection")
                .isEmpty();
        assertThat(client.itemsFor(TABLE, RUN_ID))
                .as("and it is still recorded — append-only, not ignored on write")
                .hasSize(4);
    }

    @Test
    void aSucceededRunWithALateFailureIsStillNotAFailedJob() {
        // getFailedJobs applies its status test AFTER the fold. Applied inside
        // the scan filter it would find the injected item and hand back a
        // succeeded run as failed — the same data-loss path by another route.
        runToSuccess();
        injectLate(RUN_ID, JobStatus.FAILED, "LATE_ERROR");

        assertThat(repo.getFailedJobs("system-A", EXTRACT_DATE)).isEmpty();
    }

    @Test
    void aSucceededRunWithALateRunningItemIsStillNotPending() {
        runToSuccess();
        injectLate(RUN_ID, JobStatus.RUNNING, null);

        assertThat(repo.getPendingJobs(Optional.of("system-A"))).isEmpty();
    }

    @Test
    void theFirstFailureIsTheOneThatReadsBack() {
        repo.createJob(newJob(RUN_ID));
        repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(RUN_ID, "FIRST", "quarantined rows",
                FailureStage.VALIDATION, Optional.empty());
        // FAILED -> FAILED is a legal transition (a quarantine handler and a
        // reconciliation check both mark the same run), and both items survive
        // — but the first failure's detail is the one that survives the fold.
        repo.markFailed(RUN_ID, "SECOND", "reconciliation mismatch",
                FailureStage.RECONCILIATION, Optional.empty());

        assertThat(repo.getJob(RUN_ID)).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
        assertThat(repo.getJob(RUN_ID).orElseThrow().errorCode()).contains("FIRST");
        assertThat(client.itemsFor(TABLE, RUN_ID)).hasSize(4);
    }

    // --- AD-3 / CONTRACT.md section 7: the retry is a new run ---------------

    @Test
    void aRetryAppendedAgainstAFailedRunIsRecordedButDoesNotReviveIt() {
        repo.createJob(newJob(RUN_ID));
        repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(RUN_ID, "BOOM", "failed", FailureStage.LOAD, Optional.empty());

        repo.markRetrying(RUN_ID, 1);

        assertThat(repo.getJob(RUN_ID)).get()
                .extracting(PipelineJob::status)
                .as("section 7: a retry takes a new run_id; the failed run stays failed")
                .isEqualTo(JobStatus.FAILED);
        assertThat(client.itemsFor(TABLE, RUN_ID))
                .as("the retry intent is still recorded")
                .hasSize(4);
    }

    // --- AD-2: nothing is ever mutated -------------------------------------

    @Test
    void everyStateChangeAppendsAnItemAndNoneAreReplaced() {
        repo.createJob(newJob(RUN_ID));
        repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty());
        repo.updateCostMetrics(RUN_ID, 1.25, 10L, 20L);
        repo.updateStatus(RUN_ID, JobStatus.SUCCEEDED, Optional.of(7L));

        List<Map<String, AttributeValue>> items = client.itemsFor(TABLE, RUN_ID);
        assertThat(items).hasSize(4);
        assertThat(items.get(0).get(DynamoDbJobControlRepository.ATTR_EVENT_SEQ).s())
                .as("the created item keeps the sentinel sort key, so history starts there")
                .isEqualTo(DynamoDbJobControlRepository.CREATE_EVENT_SEQ);
        assertThat(items).extracting(i -> i.get(DynamoDbJobControlRepository.ATTR_STATUS).s())
                .containsExactly("created", "running", "running", "succeeded");
    }

    @Test
    void aRunLongerThanOnePageStillProjectsCorrectly() {
        // InMemoryDynamoDb.PAGE_SIZE is 2, so this history spans three pages:
        // an unpaginated read would fold a truncated ledger.
        repo.createJob(newJob(RUN_ID));
        repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty());
        repo.updateCostMetrics(RUN_ID, 1.25, 10L, 20L);
        repo.updateCostMetrics(RUN_ID, 2.50, 30L, 40L);
        repo.updateStatus(RUN_ID, JobStatus.SUCCEEDED, Optional.of(7L));

        assertThat(client.itemsFor(TABLE, RUN_ID)).hasSizeGreaterThan(InMemoryDynamoDb.PAGE_SIZE);
        PipelineJob projected = repo.getJob(RUN_ID).orElseThrow();
        assertThat(projected.status()).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(projected.recordCount()).isEqualTo(7L);
        assertThat(projected.estimatedCostUsd())
                .as("the last pre-terminal cost append is carried forward")
                .isEqualTo(2.50);
    }

    @Test
    void costMetricsRecordedAfterATerminalStateAreWriteOnly() {
        runToSuccess();

        repo.updateCostMetrics(RUN_ID, 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob(RUN_ID).orElseThrow().estimatedCostUsd()).isEqualTo(0.0);
        // The item is in the ledger; it just is not the projected one.
        assertThat(client.itemsFor(TABLE, RUN_ID)).hasSize(4);
    }

    // --- the guard that sits in front of the append ------------------------

    @Test
    void aTransitionOutOfATerminalStateIsRejectedAndWritesNothing() {
        runToSuccess();

        assertThatThrownBy(() -> repo.markFailed(RUN_ID, "E001", "too late",
                FailureStage.LOAD, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
        assertThatThrownBy(() -> repo.markRetrying(RUN_ID, 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected one of");
        assertThatThrownBy(() -> repo.updateStatus(RUN_ID, JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected one of");

        assertThat(client.itemsFor(TABLE, RUN_ID))
                .as("three rejections, and not one of them reached the ledger")
                .hasSize(3);
    }

    @Test
    void createJobRefusesASecondHistoryForTheSameRun() {
        repo.createJob(newJob(RUN_ID));

        assertThatThrownBy(() -> repo.createJob(newJob(RUN_ID)))
                .isInstanceOf(software.amazon.awssdk.services.dynamodb.model
                        .ConditionalCheckFailedException.class);
        assertThat(client.itemsFor(TABLE, RUN_ID)).hasSize(1);
    }
}
