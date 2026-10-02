package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Objects;
import java.util.Optional;

/**
 * One pipeline run, as the console shows it. Mirrors {@link PipelineJob} (PipelineJob.java:20-43)
 * field for field, with {@code jobType} as its wire value and an added {@link #terminal()}.
 *
 * <p>A run's status is final once {@linkplain #terminal() terminal}. A failed run stays failed:
 * per {@code JobControlRepository} and {@code docs/CONTRACT.md} §7, a retry is a different run with
 * a new {@code runId}, so {@link #retryCount()} counts retries that were attempted and never means
 * this run recovered.
 */
public record RunView(
        String runId,
        String systemId,
        String pipelineName,
        LocalDate extractDate,
        JobStatus status,
        boolean terminal,
        String jobType,
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

    /** The view of {@code job}. */
    public static RunView of(PipelineJob job) {
        Objects.requireNonNull(job, "job");
        return new RunView(job.runId(), job.systemId(), job.pipelineName(), job.extractDate(),
                job.status(), isTerminal(job.status()), job.jobType().getValue(), job.entityType(),
                job.sourceFile(), job.targetTable(), job.recordCount(), job.errorCount(),
                job.retryCount(), job.failureStage(), job.errorCode(), job.errorMessage(),
                job.errorFilePath(), job.estimatedCostUsd(), job.billedBytesScanned(),
                job.billedBytesWritten(), job.createdAt(), job.updatedAt(), job.startedAt(),
                job.completedAt());
    }

    /**
     * Whether {@code status} is final: succeeded, failed or cancelled. The same set every adapter
     * projects with (BigQueryJobControlRepository.java:182-183,
     * DynamoDbJobControlRepository.java:257-258, AthenaJobControlRepository.java:179-180).
     */
    public static boolean isTerminal(JobStatus status) {
        return status == JobStatus.SUCCEEDED || status == JobStatus.FAILED
                || status == JobStatus.CANCELLED;
    }

    /**
     * One line for an operator. For a failed run it names the failure and says that a retry is a
     * separate run, so a reader never takes a retry count to mean this run recovered.
     */
    public String summary() {
        StringBuilder line = new StringBuilder()
                .append(runId).append(' ').append(status.getValue())
                .append(" (").append(pipelineName).append(", ").append(extractDate);
        entityType.ifPresent(e -> line.append(", ").append(e));
        line.append(')');
        if (status == JobStatus.FAILED) {
            failureStage.ifPresent(s -> line.append(" at ").append(s.getValue()));
            errorCode.ifPresent(c -> line.append(": ").append(c));
            line.append("; a retry runs under a new run id");
        }
        return line.toString();
    }
}
