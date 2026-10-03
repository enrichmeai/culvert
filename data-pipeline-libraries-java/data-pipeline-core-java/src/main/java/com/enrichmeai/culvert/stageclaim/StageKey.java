package com.enrichmeai.culvert.stageclaim;

import java.util.Objects;

/**
 * What a {@link com.enrichmeai.culvert.contracts.StageClaim} claims: one stage of one unit for one
 * period. The unit is the isolation key (a source, an entity, a tenant: whatever a fan-out runs in
 * parallel), the stage names a step of the pipeline (not a {@code FailureStage}, which classifies
 * errors), and the period is the slice of time the run covers, such as {@code 2026-10-01}.
 *
 * <p>All three are opaque, non-blank strings; the backend compares them exactly.
 */
public record StageKey(String unit, String stage, String period) {

    public StageKey {
        requireText(unit, "unit");
        requireText(stage, "stage");
        requireText(period, "period");
    }

    private static void requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }

    @Override
    public String toString() {
        return unit + "/" + stage + "/" + period;
    }
}
