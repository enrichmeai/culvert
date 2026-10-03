package com.enrichmeai.culvert.stageclaim;

import java.time.Instant;
import java.util.Objects;

/** The outcome of {@code StageClaim.tryClaim}: acquired, held by another, or already done. */
public sealed interface ClaimResult
        permits ClaimResult.Acquired, ClaimResult.Held, ClaimResult.Completed {

    /** The stage claimed. */
    StageKey key();

    /** The caller now holds the stage; it must {@link Claim#complete()} or {@link Claim#close()}. */
    record Acquired(Claim claim) implements ClaimResult {
        public Acquired {
            Objects.requireNonNull(claim, "claim must not be null");
        }

        @Override
        public StageKey key() {
            return claim.key();
        }
    }

    /** Another claimant held the stage for the whole wait. The stage is not done yet. */
    record Held(StageKey key) implements ClaimResult {
        public Held {
            Objects.requireNonNull(key, "key must not be null");
        }
    }

    /** The stage is already done. It is never run again under this key. */
    record Completed(StageKey key, String completedBy, Instant completedAt) implements ClaimResult {
        public Completed {
            Objects.requireNonNull(key, "key must not be null");
            Objects.requireNonNull(completedBy, "completedBy must not be null");
            Objects.requireNonNull(completedAt, "completedAt must not be null");
        }
    }
}
