package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.jobcontrol.FailedJob;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/**
 * One failed run for a system and extract date. Mirrors {@link FailedJob}. The run stays failed;
 * any retry is a separate run with its own {@code runId}.
 */
public record FailureView(
        String runId,
        String entityType,
        String failureStage,
        String errorCode,
        String errorMessage,
        Optional<String> errorFilePath,
        Instant failedAt,
        int retryCount) {

    /** The view of {@code failed}. */
    public static FailureView of(FailedJob failed) {
        Objects.requireNonNull(failed, "failed");
        return new FailureView(failed.runId(), failed.entityType(), failed.failureStage(),
                failed.errorCode(), failed.errorMessage(), failed.errorFilePath(), failed.failedAt(),
                failed.retryCount());
    }
}
