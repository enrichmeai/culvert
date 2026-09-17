package com.enrichmeai.culvert.jobcontrol;

import com.enrichmeai.culvert.contracts.JobControlRepository;

import java.io.Serializable;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * A {@link JobControlRepository} that records nothing and knows nothing —
 * for a deployment whose run state is written by <em>someone else</em>.
 *
 * <p>The case it exists for: a platform where an external orchestrator is the
 * only writer of run state. A component there is started with a run id and a
 * key, writes a run summary to that key, and exits; the orchestrator records
 * the run from the summary. Culvert's own ledger would be a second, unread
 * record of the same run, and a {@link JobControlRepository} is required —
 * {@code DefaultRuntimeContext.get} throws without one — so every such
 * deployment was hand-writing this class.
 *
 * <p><strong>Opt in, explicitly, or not at all.</strong> This class is not
 * auto-discovered and is not a fallback: it has no {@code ServiceLoader}
 * registration, and {@code DefaultRuntimeContext} never substitutes it for a
 * missing repository. A deployment that wants it calls
 * {@code register(JobControlRepository.class, new NoOpJobControlRepository())}
 * and thereby says, in its own code, that job control is recorded elsewhere.
 * A silent default here would be the failure Culvert's advisory no-ops are
 * careful to confine to advisory protocols: a run whose state nobody kept,
 * reported as fine.
 *
 * <p>Reads answer "nothing": {@link #getJob} is empty, the lists are empty,
 * {@link #cleanupPartialLoad} removes zero rows. A caller that reads job
 * control back through this class gets an honest absence, never an invented
 * status.
 */
public final class NoOpJobControlRepository implements JobControlRepository, Serializable {

    private static final long serialVersionUID = 1L;

    @Override
    public void createJob(PipelineJob job) {
        // recorded elsewhere
    }

    @Override
    public Optional<PipelineJob> getJob(String runId) {
        return Optional.empty();
    }

    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        // recorded elsewhere
    }

    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        // recorded elsewhere
    }

    @Override
    public void markRetrying(String runId, int retryCount) {
        // recorded elsewhere
    }

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        return List.of();
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        return List.of();
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        return List.of();
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate, String modelName) {
        return Optional.empty();
    }

    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        return 0;
    }

    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd, long billedBytesScanned,
                                  long billedBytesWritten) {
        // recorded elsewhere
    }
}
