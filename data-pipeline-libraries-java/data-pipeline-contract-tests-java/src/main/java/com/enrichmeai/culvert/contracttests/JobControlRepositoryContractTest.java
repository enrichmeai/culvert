package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link JobControlRepository} implementation must pass.
 *
 * <h2>Why this exists</h2>
 * <p>The external review's finding #4 argued that job control's use of
 * {@code UPDATE … SET status} blocked Athena entirely — Athena has no DML on
 * non-Iceberg tables. The fix was to make the store append-only. This suite is
 * what turns "Athena can now implement this" from an argument into something
 * falsifiable: any backend that passes is implementable on a store with no
 * {@code UPDATE} at all.
 *
 * <h2>Behavioural, never SQL inspection</h2>
 * <p>Nothing here greps a query string. A backend could remove every literal
 * {@code UPDATE} and still return last-write-wins from its reads, which would
 * satisfy the letter of append-only and none of its point. These tests append
 * events and then ask the repository what the run's state <em>is</em>.
 *
 * <h2>The rule being pinned</h2>
 * <p><strong>A terminal state is immutable, and the earliest terminal wins.</strong>
 * That is not a stylistic preference. Removing compare-and-set without it
 * creates a data-loss path: a late failure flips a succeeded run to
 * {@code FAILED}; {@code FAILED} is retryable; the retry path then deletes the
 * rows that successful run loaded. {@link #successThenLateFailureStaysSucceeded()}
 * is the guard, and it must fail if terminal precedence is ever removed.
 *
 * <p>Note the retry model: a failed run is never resurrected in place. §7
 * requires a retry to take a new {@code run_id}, so
 * {@link #aFailedRunStaysFailedAndTheRetryIsANewRun} asserts the old run stays
 * {@code FAILED} and the retry succeeds as a separate run.
 *
 * <p>Subclasses supply a repository whose ledger starts empty for each unique
 * {@code runId}. Implementations that cannot support a method may override the
 * corresponding {@code supports…} hook.
 */
public abstract class JobControlRepositoryContractTest {

    /** A repository under test. Must be usable for arbitrary fresh run ids. */
    protected abstract JobControlRepository repository();

    /**
     * Whether this backend supports {@link JobControlRepository#markRetrying}.
     * Defaults to true; override and explain if a backend genuinely cannot.
     */
    protected boolean supportsRetry() {
        return true;
    }

    /** The system id this backend's fixtures use. */
    protected String systemId() {
        return "Generic";
    }

    private String freshRunId() {
        return "contract-" + UUID.randomUUID();
    }

    private PipelineJob newJob(String runId) {
        return PipelineJob.builder(runId, systemId(), "contract_pipeline",
                        LocalDate.of(2026, 9, 9), JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customers")
                .targetTable("proj.odp.customers")
                .build();
    }

    private JobStatus statusOf(String runId) {
        return repository().getJob(runId)
                .map(PipelineJob::status)
                .orElseThrow(() -> new AssertionError("no job found for " + runId));
    }

    /**
     * Append a row straight to the ledger, bypassing transition validation.
     *
     * <p>Required so the projection is tested rather than believed. Without it,
     * {@link #successThenLateFailureStaysSucceeded()} can pass on a backend
     * whose transition guard rejects the late failure before the ranking is
     * ever consulted — the assertion then holds for the wrong reason, and a
     * completely broken projection would ship green. That was observed for
     * real: stripping terminal precedence from one backend left that test
     * passing, because its guard short-circuited first.
     *
     * <p>The default <strong>fails</strong> rather than skipping. A backend
     * that silently opts out of the projection check is exactly the "guard that
     * cannot fail" this suite exists to prevent.
     */
    protected void appendRaw(String runId, JobStatus status) {
        throw new AssertionError(getClass().getSimpleName()
                + " must override appendRaw(runId, status). Without it the projection "
                + "is never exercised directly, and a broken ranking can pass this suite "
                + "on the strength of the transition guard alone.");
    }

    @Test
    void theProjectionItselfKeepsTheEarliestTerminalState() {
        // Goes AROUND the transition guard on purpose. This is the only test
        // that isolates the ranking: it writes a contradicting terminal row the
        // guard would have refused, then asks what the run's state is.
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(runId, JobStatus.SUCCEEDED, Optional.of(3L));

        appendRaw(runId, JobStatus.FAILED);

        assertThat(statusOf(runId))
                .as("the PROJECTION must keep the earliest terminal state even when a "
                        + "contradicting row reaches the ledger — the guard is not the "
                        + "only thing standing between a late failure and a deleted table")
                .isEqualTo(JobStatus.SUCCEEDED);
    }

    @Test
    void aCreatedJobIsReadableWithTheStatusItWasCreatedIn() {
        String runId = freshRunId();
        repository().createJob(newJob(runId));

        assertThat(repository().getJob(runId)).isPresent();
        assertThat(statusOf(runId)).isEqualTo(JobStatus.CREATED);
    }

    @Test
    void failureThenSuccessReadsFailed() {
        // The original defect: markFailed recorded a mismatch, then
        // updateStatus(SUCCEEDED) overwrote it, and a load that never
        // reconciled reported green in the one table an operator checks.
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(runId, "RECONCILIATION_MISMATCH", "counts did not add up",
                FailureStage.RECONCILIATION, Optional.empty());

        assertThat(statusOf(runId))
                .as("a recorded failure must survive anything appended after it")
                .isEqualTo(JobStatus.FAILED);
    }

    @Test
    void successThenLateFailureStaysSucceeded() {
        // THE DATA-LOSS GUARD. If a late failure could flip a succeeded run to
        // FAILED, that run becomes retryable, and the retry path deletes the
        // rows it successfully loaded. A terminal state must be immutable.
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(runId, JobStatus.SUCCEEDED, Optional.of(3L));

        // A late, contradicting failure. Recording it is fine; letting it win
        // is not. Backends may reject it outright or accept and ignore it —
        // both satisfy the contract, so tolerate either.
        try {
            repo.markFailed(runId, "LATE_ERROR", "arrived after the run finished",
                    FailureStage.UNKNOWN, Optional.empty());
        } catch (RuntimeException expectedOnSomeBackends) {
            // A backend that refuses the transition outright is also correct.
        }

        assertThat(statusOf(runId))
                .as("a terminal state is immutable — otherwise the retry path "
                        + "deletes the data this run loaded")
                .isEqualTo(JobStatus.SUCCEEDED);
    }

    @Test
    void aSucceededRunIsNotReportedAsPending() {
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(runId, JobStatus.SUCCEEDED, Optional.of(1L));

        assertThat(repo.getPendingJobs(Optional.of(systemId())))
                .as("pending must reflect projected state, not every row ever written")
                .noneMatch(job -> job.runId().equals(runId));
    }

    @Test
    void aFailedRunIsNotReportedAsPending() {
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(runId, "BOOM", "failed", FailureStage.LOAD, Optional.empty());

        assertThat(repo.getPendingJobs(Optional.of(systemId())))
                .noneMatch(job -> job.runId().equals(runId));
    }

    @Test
    void aRunningJobIsReportedAsPending() {
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());

        assertThat(repo.getPendingJobs(Optional.of(systemId())))
                .anyMatch(job -> job.runId().equals(runId));
    }

    @Test
    void repeatedFailuresKeepTheRunFailed() {
        String runId = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(runId));
        repo.updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(runId, "FIRST", "first failure", FailureStage.LOAD, Optional.empty());
        try {
            repo.markFailed(runId, "SECOND", "second failure",
                    FailureStage.LOAD, Optional.empty());
        } catch (RuntimeException tolerated) {
            // Some backends reject a second failure; that is acceptable.
        }

        assertThat(statusOf(runId)).isEqualTo(JobStatus.FAILED);
    }

    @Test
    void aFailedRunStaysFailedAndTheRetryIsANewRun() {
        // CORRECTED 2026-09-09. This test previously asserted that markRetrying
        // moves a run out of FAILED. That contradicted the contract it exists
        // to enforce: docs/CONTRACT.md §7 requires a retried pipeline to take a
        // NEW run_id, recording the previous one in the RETRY_ATTEMPTED event's
        // payload.previous_run_id. A failed run is not resurrected in place —
        // it stays failed, and the retry is a different run.
        //
        // The contradiction was caught by a backend that could not satisfy both
        // rules at once, which is exactly what a shared contract test is for.
        if (!supportsRetry()) {
            return;
        }
        String failedRun = freshRunId();
        JobControlRepository repo = repository();
        repo.createJob(newJob(failedRun));
        repo.updateStatus(failedRun, JobStatus.RUNNING, Optional.empty());
        repo.markFailed(failedRun, "BOOM", "failed", FailureStage.LOAD, Optional.empty());

        // Recording the retry intent against the old run is allowed; backends
        // may also reject it. Either way it must NOT resurrect the run.
        try {
            repo.markRetrying(failedRun, 1);
        } catch (RuntimeException tolerated) {
            // A backend that refuses the transition outright is also correct.
        }

        assertThat(statusOf(failedRun))
                .as("§7: the failed run stays failed; a retry does not revive it "
                        + "in place, or a late row could flip a terminal state")
                .isEqualTo(JobStatus.FAILED);

        // The retry itself is a new run, and it succeeds independently.
        String retryRun = freshRunId();
        repo.createJob(newJob(retryRun));
        repo.updateStatus(retryRun, JobStatus.RUNNING, Optional.empty());
        repo.updateStatus(retryRun, JobStatus.SUCCEEDED, Optional.of(3L));

        assertThat(statusOf(retryRun)).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(statusOf(failedRun))
                .as("the original run is untouched by its retry")
                .isEqualTo(JobStatus.FAILED);
    }

    @Test
    void anUnknownRunIdReadsAsAbsentRatherThanThrowing() {
        assertThat(repository().getJob(freshRunId()))
                .as("absent is a normal answer; callers branch on it")
                .isEmpty();
    }

    @Test
    void updatingAnUnknownRunIsRejected() {
        // Silently creating a row here would let a typo'd runId look like a
        // healthy run that nothing ever started.
        assertThatThrownBy(() -> repository().updateStatus(
                freshRunId(), JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(RuntimeException.class);
    }
}
