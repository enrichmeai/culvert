package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * Pipeline-job state-machine contract.
 *
 * <p><strong>The ledger is append-only.</strong> A transition records a new
 * event; it does not mutate the run's existing row, and concurrent appends for
 * the same {@code runId} may interleave. No cross-row transaction is required
 * — which is exactly what makes this implementable on a store with no
 * {@code UPDATE} at all, such as Athena over non-Iceberg tables.
 *
 * <p>Ordering is therefore resolved on <em>read</em>, by projection:
 * <strong>a terminal state is immutable and the earliest terminal event
 * wins.</strong> A late failure cannot flip a run that already succeeded —
 * without that rule, dropping compare-and-set opens a data-loss path, because
 * a flipped run becomes retryable and the retry deletes the rows the
 * successful run loaded. Implementations MUST pass
 * {@code JobControlRepositoryContractTest}, which pins the rule behaviourally
 * rather than by SQL inspection.
 *
 * <p>A failed run is never resurrected in place. Per {@code docs/CONTRACT.md}
 * §7 a retry takes a NEW {@code runId}, recording the previous one in the
 * {@code RETRY_ATTEMPTED} event's {@code payload.previous_run_id}, so
 * {@link #markRetrying} records intent and does not move a run out of
 * {@code FAILED}.
 *
 * <p><strong>Honest limitation — {@link #createJob} is not uniformly
 * atomic.</strong> BigQuery ({@code MERGE … WHEN NOT MATCHED}) and DynamoDB
 * ({@code attribute_not_exists}) both reject a duplicate {@code runId}
 * server-side. Athena cannot: it issues a plain {@code INSERT}, so two callers
 * racing on one {@code runId} both succeed and the projection de-duplicates
 * them. Do not rely on {@code createJob} as a distributed lock.
 *
 * <p>Java mirror of the Python {@code JobControlRepository} Protocol. The
 * eleven methods match the existing Python repository's public surface
 * one-for-one, with no GCP type leakage in arguments or return types.
 */
public interface JobControlRepository {

    /** Insert a new pipeline-job row in {@link JobStatus#CREATED} state. */
    void createJob(PipelineJob job);

    /** Return the job with this {@code runId}, or empty if not found. */
    Optional<PipelineJob> getJob(String runId);

    /**
     * Transition a job to a new status.
     *
     * @param totalRecords Optionally record final record count when the
     *                     status is terminal ({@code SUCCEEDED}/{@code FAILED}).
     */
    void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords);

    /**
     * Mark a job as failed with structured error context.
     *
     * <p>{@code errorFilePath} is an opaque URI ({@code gs://}, {@code s3://}) to
     * the quarantined records that caused the failure; the framework does not
     * parse it.
     */
    void markFailed(String runId, String errorCode, String errorMessage,
                    FailureStage failureStage, Optional<String> errorFilePath);

    /** Mark a job as RETRYING and bump its retry counter. */
    void markRetrying(String runId, int retryCount);

    /** List jobs in CREATED or RUNNING status, optionally filtered to a single system. */
    List<PipelineJob> getPendingJobs(Optional<String> systemId);

    /** Per-entity status snapshot for a given system and extract date. */
    List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate);

    /** List failed jobs for a system + extract date. */
    List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate);

    /** Return the FDP-model run status for this system + date + model. */
    Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate, String modelName);

    /**
     * Delete records partially loaded by a failed run from {@code tableId}.
     *
     * @return The number of rows removed.
     */
    int cleanupPartialLoad(String runId, String tableId);

    /** Attach cost metrics to the job row. Called by the cost-tracker after compute completes. */
    void updateCostMetrics(String runId, double estimatedCostUsd,
                           long billedBytesScanned, long billedBytesWritten);
}
