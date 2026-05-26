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
 * <p>Implementations are expected to be transactional within a single
 * {@code runId} (state transitions cannot interleave with a concurrent
 * update of the same run).
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
