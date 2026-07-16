package com.enrichmeai.culvert.jobcontrol;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Optional;

/**
 * A single pipeline-job ledger entry. Every record processed by the framework
 * is associated with exactly one {@code PipelineJob} via {@code runId}.
 *
 * <p>Mirrors the Python {@code PipelineJob} dataclass
 * ({@code data_pipeline_core.job_control_api.models}) — both languages
 * share the {@code job_control.pipeline_jobs} ledger schema.
 *
 * <p>Note: this record uses a builder because seventeen positional arguments
 * would be hostile to callers. Use {@link #builder(String, String, String, LocalDate, JobStatus)}.
 */
public record PipelineJob(
        String runId,
        String systemId,
        String pipelineName,
        LocalDate extractDate,
        JobStatus status,
        JobType jobType,
        Optional<String> entityType,
        Optional<String> sourceFile,
        Optional<String> targetTable,
        long recordCount,
        long errorCount,
        int retryCount,
        Optional<FailureStage> failureStage,
        Optional<String> errorCode,
        Optional<String> errorMessage,
        Optional<String> errorFilePath,
        double estimatedCostUsd,
        long billedBytesScanned,
        long billedBytesWritten,
        Instant createdAt,
        Instant updatedAt,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    public PipelineJob {
        if (runId == null) throw new IllegalArgumentException("runId");
        if (systemId == null) throw new IllegalArgumentException("systemId");
        if (pipelineName == null) throw new IllegalArgumentException("pipelineName");
        if (extractDate == null) throw new IllegalArgumentException("extractDate");
        if (status == null) throw new IllegalArgumentException("status");
        if (jobType == null) jobType = JobType.INGESTION;
        if (entityType == null) entityType = Optional.empty();
        if (sourceFile == null) sourceFile = Optional.empty();
        if (targetTable == null) targetTable = Optional.empty();
        if (failureStage == null) failureStage = Optional.empty();
        if (errorCode == null) errorCode = Optional.empty();
        if (errorMessage == null) errorMessage = Optional.empty();
        if (errorFilePath == null) errorFilePath = Optional.empty();
        if (startedAt == null) startedAt = Optional.empty();
        if (completedAt == null) completedAt = Optional.empty();
        if (createdAt == null) createdAt = Instant.now();
        if (updatedAt == null) updatedAt = createdAt;
    }

    public static Builder builder(String runId, String systemId, String pipelineName,
                                  LocalDate extractDate, JobStatus status) {
        return new Builder(runId, systemId, pipelineName, extractDate, status);
    }

    public static final class Builder {
        private final String runId;
        private final String systemId;
        private final String pipelineName;
        private final LocalDate extractDate;
        private final JobStatus status;
        private JobType jobType = JobType.INGESTION;
        private Optional<String> entityType = Optional.empty();
        private Optional<String> sourceFile = Optional.empty();
        private Optional<String> targetTable = Optional.empty();
        private long recordCount;
        private long errorCount;
        private int retryCount;
        private Optional<FailureStage> failureStage = Optional.empty();
        private Optional<String> errorCode = Optional.empty();
        private Optional<String> errorMessage = Optional.empty();
        private Optional<String> errorFilePath = Optional.empty();
        private double estimatedCostUsd;
        private long billedBytesScanned;
        private long billedBytesWritten;
        private Instant createdAt = Instant.now();
        private Instant updatedAt;
        private Optional<Instant> startedAt = Optional.empty();
        private Optional<Instant> completedAt = Optional.empty();

        private Builder(String runId, String systemId, String pipelineName,
                        LocalDate extractDate, JobStatus status) {
            this.runId = runId;
            this.systemId = systemId;
            this.pipelineName = pipelineName;
            this.extractDate = extractDate;
            this.status = status;
        }

        public Builder jobType(JobType v) { this.jobType = v; return this; }
        public Builder entityType(String v) { this.entityType = Optional.ofNullable(v); return this; }
        public Builder sourceFile(String v) { this.sourceFile = Optional.ofNullable(v); return this; }
        public Builder targetTable(String v) { this.targetTable = Optional.ofNullable(v); return this; }
        public Builder recordCount(long v) { this.recordCount = v; return this; }
        public Builder errorCount(long v) { this.errorCount = v; return this; }
        public Builder retryCount(int v) { this.retryCount = v; return this; }
        public Builder failureStage(FailureStage v) { this.failureStage = Optional.ofNullable(v); return this; }
        public Builder errorCode(String v) { this.errorCode = Optional.ofNullable(v); return this; }
        public Builder errorMessage(String v) { this.errorMessage = Optional.ofNullable(v); return this; }
        public Builder errorFilePath(String v) { this.errorFilePath = Optional.ofNullable(v); return this; }
        public Builder estimatedCostUsd(double v) { this.estimatedCostUsd = v; return this; }
        public Builder billedBytesScanned(long v) { this.billedBytesScanned = v; return this; }
        public Builder billedBytesWritten(long v) { this.billedBytesWritten = v; return this; }
        public Builder createdAt(Instant v) { this.createdAt = v; return this; }
        public Builder updatedAt(Instant v) { this.updatedAt = v; return this; }
        public Builder startedAt(Instant v) { this.startedAt = Optional.ofNullable(v); return this; }
        public Builder completedAt(Instant v) { this.completedAt = Optional.ofNullable(v); return this; }

        public PipelineJob build() {
            return new PipelineJob(runId, systemId, pipelineName, extractDate, status,
                    jobType, entityType, sourceFile, targetTable, recordCount, errorCount,
                    retryCount, failureStage, errorCode, errorMessage, errorFilePath,
                    estimatedCostUsd, billedBytesScanned, billedBytesWritten,
                    createdAt, updatedAt == null ? createdAt : updatedAt,
                    startedAt, completedAt);
        }
    }
}
