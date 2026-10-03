package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** An FDP model's run status for a system and extract date. Mirrors {@link FdpJobStatus}. */
public record FdpRunView(
        String runId,
        String modelName,
        String status,
        long recordCount,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    /** The view of {@code status}. */
    public static FdpRunView of(FdpJobStatus status) {
        Objects.requireNonNull(status, "status");
        return new FdpRunView(status.runId(), status.modelName(), status.status(),
                status.recordCount(), status.startedAt(), status.completedAt());
    }
}
