package com.enrichmeai.culvert.governance;

import java.util.Optional;

/**
 * Policy: this table is retained for this many days.
 *
 * <p>{@code legalHold} overrides the retention window — when true, no deletion
 * is permitted regardless of age. {@code purpose} is a free-text reason that
 * appears in deletion audit records.
 *
 * <p>Mirrors the Python {@code RetentionPolicy} dataclass.
 *
 * @param retentionDays How many days the data must be retained.
 * @param legalHold     If true, no deletion is permitted regardless of age.
 * @param purpose       Optional free-text reason for the policy.
 */
public record RetentionPolicy(int retentionDays, boolean legalHold, Optional<String> purpose) {

    public RetentionPolicy {
        if (retentionDays < 0) {
            throw new IllegalArgumentException("retentionDays must be non-negative");
        }
        if (purpose == null) {
            purpose = Optional.empty();
        }
    }

    /** Convenience factory: a retention window without legal hold or purpose. */
    public static RetentionPolicy ofDays(int days) {
        return new RetentionPolicy(days, false, Optional.empty());
    }
}
