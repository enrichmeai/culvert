package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * In-memory {@link JobControlRepository} test double that records every call,
 * mirroring {@code deployments/reference-e2e-gcp}'s
 * {@code com.enrichmeai.culvert.e2e.dq.StubJobControlRepository} (T14.5
 * pattern) but scoped to the subset of the interface this deployment calls
 * ({@code createJob}, {@code updateStatus}, {@code markFailed}).
 */
public final class RecordingJobControlRepository implements JobControlRepository {

    private final Map<String, PipelineJob> jobs = new LinkedHashMap<>();
    public final List<StatusUpdate> statusUpdates = new ArrayList<>();
    public final List<MarkFailedCall> markFailedCalls = new ArrayList<>();

    public record StatusUpdate(String runId, JobStatus status, Optional<Long> totalRecords) {
    }

    public record MarkFailedCall(String runId, String errorCode, String errorMessage,
                                  FailureStage failureStage, Optional<String> errorFilePath) {
    }

    public Optional<PipelineJob> job(String runId) {
        return Optional.ofNullable(jobs.get(runId));
    }

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
        statusUpdates.add(new StatusUpdate(runId, status, totalRecords));
    }

    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        markFailedCalls.add(new MarkFailedCall(runId, errorCode, errorMessage, failureStage, errorFilePath));
    }

    @Override
    public void markRetrying(String runId, int retryCount) {
        throw new UnsupportedOperationException("stub: markRetrying not used by this deployment");
    }

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        throw new UnsupportedOperationException("stub: getPendingJobs not used by this deployment");
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        throw new UnsupportedOperationException("stub: getEntityStatus not used by this deployment");
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        throw new UnsupportedOperationException("stub: getFailedJobs not used by this deployment");
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate, String modelName) {
        throw new UnsupportedOperationException("stub: getFdpJobStatus not used by this deployment");
    }

    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        throw new UnsupportedOperationException("stub: cleanupPartialLoad not used by this deployment");
    }

    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        // advisory only — no-op
    }
}
