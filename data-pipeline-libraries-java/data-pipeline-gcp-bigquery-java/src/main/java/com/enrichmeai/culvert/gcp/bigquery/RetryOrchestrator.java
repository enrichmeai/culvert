package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;

import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * Stateless helper that sequences the retry lifecycle for a failed pipeline run.
 *
 * <p>Sequences: check the run is eligible to retry → detect prior partial load →
 * {@code cleanupPartialLoad} → {@code markRetrying} → return cleared state for the caller to
 * re-submit the pipeline. This keeps the orchestration logic out of the repository
 * implementation and allows deterministic unit-testing with a stub
 * {@link JobControlRepository}.
 *
 * <h2>Eligibility is checked before anything is deleted</h2>
 * <p>The eligibility check comes first on purpose. {@code markRetrying} reads the run's
 * projected state and rejects a prior state it may not leave (see
 * {@link BigQueryJobControlRepository}), so an ineligible run — a {@code SUCCEEDED} one,
 * say — would be rejected there anyway; but by that point {@code cleanupPartialLoad} would
 * already have deleted the rows that run legitimately loaded, leaving an emptied table behind
 * a job record still reading SUCCEEDED. Checking first means an ineligible retry changes
 * nothing at all.
 *
 * <p>The append-only ledger closes the other half of that hole. Under AD-3 the first terminal
 * state a run reaches is final, so a {@code failed} row appended after a run succeeded does
 * not make the run read {@code FAILED} — and therefore cannot route it into this class at
 * all. Recency-based state would: it would flip the run to {@code FAILED}, which is
 * retryable, and {@code cleanupPartialLoad} would delete the data the successful run had just
 * loaded.
 *
 * <h2>Idempotency guarantee</h2>
 * <p>If the job is already in {@link JobStatus#RETRYING} state (detected via {@link
 * JobControlRepository#getJob(String)}), the orchestrator does not call {@code markRetrying}
 * again and returns the current retry counter unchanged. This prevents double-incrementing
 * when a caller retries an already-in-progress re-run.
 *
 * <h2>Target-table cleanup</h2>
 * <p>The orchestrator reads {@link PipelineJob#targetTable()} from the job record. If no
 * target table is recorded (Optional is empty), the cleanup step is skipped and
 * {@link RetryResult#rowsCleaned()} returns 0. The job-control status is still updated.
 *
 * <h2>Schema contract</h2>
 * <p>Every pipeline-written target table must contain a {@code _run_id STRING} column populated
 * with the run's identifier at load time. {@code cleanupPartialLoad} issues
 * {@code DELETE FROM <table> WHERE _run_id = @run_id} against that column. See the module
 * README's "Retry &amp; partial-load cleanup" section.
 *
 * <p>Sprint-14 deliverable for issue
 * <a href="https://github.com/enrichmeai/culvert/issues/75">#75</a> (T14.3).
 */
public final class RetryOrchestrator {

    private final JobControlRepository repository;

    /**
     * Primary constructor.
     *
     * @param repository The job-control repository used for state transitions and cleanup.
     *                   Required; must not be null.
     * @throws NullPointerException if {@code repository} is null.
     */
    public RetryOrchestrator(JobControlRepository repository) {
        this.repository = Objects.requireNonNull(repository, "repository must not be null");
    }

    /**
     * Prepares a failed pipeline run for re-execution.
     *
     * <ol>
     *   <li>Load the current job state via {@link JobControlRepository#getJob(String)}.
     *   <li>If the job is already {@link JobStatus#RETRYING}, return its current state
     *       without modifying any counters (idempotent re-run).
     *   <li>If the job has a {@code targetTable}, call
     *       {@link JobControlRepository#cleanupPartialLoad(String, String)} to delete
     *       rows inserted by the failed run.
     *   <li>Call {@link JobControlRepository#markRetrying(String, int)} with the incremented
     *       retry counter.
     *   <li>Return a {@link RetryResult} carrying the final counter and cleanup row count.
     * </ol>
     *
     * @param runId The run identifier of the failed pipeline job. Required.
     * @return A {@link RetryResult} describing the post-retry state.
     * @throws NullPointerException     if {@code runId} is null.
     * @throws IllegalStateException    if no job exists for the given {@code runId}, or the
     *                                  job is in a state that may not be retried (e.g.
     *                                  {@code SUCCEEDED}). Nothing is deleted in that case.
     */
    public RetryResult prepareRetry(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");

        Optional<PipelineJob> jobOpt = repository.getJob(runId);
        PipelineJob job = jobOpt.orElseThrow(() ->
                new IllegalStateException("No job found for runId: " + runId));

        // Idempotency guard: if already RETRYING, don't double-increment.
        if (job.status() == JobStatus.RETRYING) {
            return new RetryResult(runId, job.retryCount(), 0);
        }

        // Eligibility guard, BEFORE any deletion — see the class javadoc. Same transition
        // table markRetrying enforces, asked one step earlier.
        Set<JobStatus> retryable =
                BigQueryJobControlRepository.allowedPriorStates(JobStatus.RETRYING);
        if (!retryable.contains(job.status())) {
            throw new IllegalStateException("Cannot retry runId=" + runId + ": status is "
                    + job.status() + ", expected one of " + retryable
                    + ". Nothing was deleted.");
        }

        // Cleanup partial load if a target table is recorded.
        int rowsCleaned = 0;
        Optional<String> targetTable = job.targetTable();
        if (targetTable.isPresent()) {
            rowsCleaned = repository.cleanupPartialLoad(runId, targetTable.get());
        }

        // Mark RETRYING with incremented counter.
        int newRetryCount = job.retryCount() + 1;
        repository.markRetrying(runId, newRetryCount);

        return new RetryResult(runId, newRetryCount, rowsCleaned);
    }

    /**
     * The result of a {@link #prepareRetry(String)} call.
     *
     * @param runId        The run identifier.
     * @param retryCount   The retry counter after the orchestration step.
     * @param rowsCleaned  The number of rows removed from the target table.
     *                     Zero when no target table was recorded.
     */
    public record RetryResult(String runId, int retryCount, int rowsCleaned) {
    }
}
