package com.enrichmeai.culvert.e2e.dq;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * In-memory {@link JobControlRepository} stub used by the S14 DQ E2E slice.
 *
 * <p>Implements the subset of the interface called by
 * {@link com.enrichmeai.culvert.gcp.gcs.QuarantineHandler} ({@code markFailed})
 * and {@link com.enrichmeai.culvert.gcp.bigquery.RetryOrchestrator}
 * ({@code getJob}, {@code markRetrying}, {@code cleanupPartialLoad}).
 *
 * <h2>Target-table rows model</h2>
 * <p>The "target table" is modelled as a list of run-ID strings:
 * {@code targetTableRows}. Each simulated insert appends the run-ID once.
 * {@code cleanupPartialLoad} removes all entries matching the run-ID and
 * returns the removal count, which proves idempotent re-run (second cleanup
 * removes 0 rows).
 *
 * <p>Sprint-14 / issue #82 (T14.5) stub — not a production repository.
 */
final class StubJobControlRepository implements JobControlRepository {

    /** Job ledger: runId → PipelineJob */
    private final Map<String, PipelineJob> jobs = new LinkedHashMap<>();

    /** Captures every {@code markFailed} call for assertion. */
    final List<MarkFailedCall> markFailedCalls = new ArrayList<>();

    /** Tracks transition history: runId → final status */
    final Map<String, JobStatus> statusHistory = new LinkedHashMap<>();

    /** Simulated target-table rows (each entry is a run-ID, representing one inserted row). */
    final List<String> targetTableRows = new ArrayList<>();

    // -----------------------------------------------------------------------
    // Test-setup helpers
    // -----------------------------------------------------------------------

    /** Pre-register a job so {@code getJob(runId)} returns it. */
    void seedJob(PipelineJob job) {
        jobs.put(job.runId(), job);
    }

    /** Simulate a row having been written to the target table for {@code runId}. */
    void insertTargetRow(String runId) {
        targetTableRows.add(runId);
    }

    /** Returns the count of target-table rows still present for {@code runId}. */
    int targetRowCount(String runId) {
        return (int) targetTableRows.stream().filter(runId::equals).count();
    }

    // -----------------------------------------------------------------------
    // Used methods
    // -----------------------------------------------------------------------

    @Override
    public void createJob(PipelineJob job) {
        jobs.put(job.runId(), job);
    }

    @Override
    public Optional<PipelineJob> getJob(String runId) {
        return Optional.ofNullable(jobs.get(runId));
    }

    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        statusHistory.put(runId, status);
        PipelineJob existing = jobs.get(runId);
        if (existing != null) {
            // Rebuild the record with updated status. PipelineJob is a record so we
            // reconstruct via the builder. We only need this for retry idempotency
            // (detecting RETRYING status) — copy the other fields unchanged.
            jobs.put(runId, PipelineJob.builder(
                    existing.runId(), existing.systemId(), existing.pipelineName(),
                    existing.extractDate(), status)
                    .jobType(existing.jobType())
                    .targetTable(existing.targetTable().orElse(null))
                    .retryCount(existing.retryCount())
                    .build());
        }
    }

    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        markFailedCalls.add(new MarkFailedCall(runId, errorCode, errorMessage,
                failureStage, errorFilePath));
    }

    @Override
    public void markRetrying(String runId, int retryCount) {
        PipelineJob existing = jobs.get(runId);
        if (existing != null) {
            jobs.put(runId, PipelineJob.builder(
                    existing.runId(), existing.systemId(), existing.pipelineName(),
                    existing.extractDate(), JobStatus.RETRYING)
                    .jobType(existing.jobType())
                    .targetTable(existing.targetTable().orElse(null))
                    .retryCount(retryCount)
                    .build());
        }
    }

    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        int before = targetTableRows.size();
        targetTableRows.removeIf(runId::equals);
        return before - targetTableRows.size();
    }

    // -----------------------------------------------------------------------
    // Unused methods — throw to catch accidental calls
    // -----------------------------------------------------------------------

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        throw new UnsupportedOperationException("stub: getPendingJobs not used by S14 slice");
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        throw new UnsupportedOperationException("stub: getEntityStatus not used by S14 slice");
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        throw new UnsupportedOperationException("stub: getFailedJobs not used by S14 slice");
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                   String modelName) {
        throw new UnsupportedOperationException("stub: getFdpJobStatus not used by S14 slice");
    }

    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        // advisory only — no-op in this stub
    }

    // -----------------------------------------------------------------------
    // Value holder for markFailed captures
    // -----------------------------------------------------------------------

    record MarkFailedCall(
            String runId,
            String errorCode,
            String errorMessage,
            FailureStage failureStage,
            Optional<String> errorFilePath) {
    }
}
