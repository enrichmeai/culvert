package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.jobcontrol.EntityStatus;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** One entity's latest status for a system and extract date. Mirrors {@link EntityStatus}. */
public record EntityStatusView(
        String entityType,
        String status,
        String runId,
        long recordCount,
        long errorCount,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    /** The view of {@code status}. */
    public static EntityStatusView of(EntityStatus status) {
        Objects.requireNonNull(status, "status");
        return new EntityStatusView(status.entityType(), status.status(), status.runId(),
                status.recordCount(), status.errorCount(), status.startedAt(), status.completedAt());
    }
}
