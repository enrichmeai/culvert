package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link StageClaim} implementation must pass.
 *
 * <p><strong>Deterministic, not statistical.</strong> No test spawns threads and hopes for a race.
 * Two claimants are driven in a fixed order from one thread: A acquires and holds, then B tries the
 * same key with a bounded wait. B is guaranteed to wait, because A holds the claim for B's whole
 * call. B's outcome is then asserted exactly. Each step happens in a known order, so a pass means
 * the guarantee held, not that the race did not occur.
 *
 * <p>Subclasses provide {@link #stageClaim()}. Each {@code tryClaim} call must be an independent
 * claimant (a separate session, connection or lock owner), even from the same thread. An
 * implementation whose lock is re-entrant per thread would let B acquire what A holds, and fails here.
 */
public abstract class StageClaimContractTest {

    /** The claim under test. Keys are fresh per test, so state may persist between tests. */
    protected abstract StageClaim stageClaim();

    /** How long B waits for A in the held cases. Long enough to be a real wait, short enough to run fast. */
    protected Duration heldWait() {
        return Duration.ofMillis(300);
    }

    private static StageKey freshKey() {
        return new StageKey("unit-" + UUID.randomUUID(), "load", "2026-10-01");
    }

    private Claim acquire(StageKey key, String claimant) {
        ClaimResult r = stageClaim().tryClaim(key, claimant, Duration.ZERO);
        assertThat(r).as("%s should acquire %s", claimant, key).isInstanceOf(ClaimResult.Acquired.class);
        return ((ClaimResult.Acquired) r).claim();
    }

    @Test
    void aFreshStageIsAcquired() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            assertThat(a.key()).isEqualTo(key);
            assertThat(a.claimant()).isEqualTo("A");
        }
    }

    @Test
    void whileAHoldsBWaitsAndIsHeld() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            assertThat(a.key()).isEqualTo(key);
            long start = System.nanoTime();
            ClaimResult b = stageClaim().tryClaim(key, "B", heldWait());
            long waitedMs = Duration.ofNanos(System.nanoTime() - start).toMillis();

            assertThat(b).isEqualTo(new ClaimResult.Held(key));
            assertThat(waitedMs).as("B must block for its wait, not return at once")
                    .isGreaterThanOrEqualTo(heldWait().toMillis() / 2);
        }
    }

    @Test
    void whileAHoldsAZeroWaitClaimIsHeldAtOnce() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            assertThat(a.claimant()).isEqualTo("A");
            assertThat(stageClaim().tryClaim(key, "B", Duration.ZERO)).isEqualTo(new ClaimResult.Held(key));
        }
    }

    @Test
    void afterACompletesBSeesCompletedAndNeverRunsTheStage() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            assertThat(stageClaim().tryClaim(key, "B", Duration.ZERO)).isInstanceOf(ClaimResult.Held.class);
            a.complete();
        }
        ClaimResult b = stageClaim().tryClaim(key, "B", heldWait());
        assertThat(b).isInstanceOf(ClaimResult.Completed.class);
        ClaimResult.Completed done = (ClaimResult.Completed) b;
        assertThat(done.key()).isEqualTo(key);
        assertThat(done.completedBy()).isEqualTo("A");
        assertThat(stageClaim().tryClaim(key, "A", Duration.ZERO))
                .as("not even the claimant that completed it runs it again")
                .isInstanceOf(ClaimResult.Completed.class);
    }

    @Test
    void anAbandonedClaimIsAcquiredByTheNextClaimant() {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        a.close(); // abandoned: A stopped without completing

        try (Claim b = acquire(key, "B")) {
            assertThat(b.claimant()).isEqualTo("B");
            b.complete();
        }
        assertThat(((ClaimResult.Completed) stageClaim().tryClaim(key, "C", Duration.ZERO)).completedBy())
                .isEqualTo("B");
    }

    @Test
    void differentKeysDoNotContend() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A");
             Claim otherUnit = acquire(new StageKey(key.unit() + "-x", key.stage(), key.period()), "B");
             Claim otherStage = acquire(new StageKey(key.unit(), "transform", key.period()), "C");
             Claim otherPeriod = acquire(new StageKey(key.unit(), key.stage(), "2026-10-02"), "D")) {
            assertThat(otherUnit.key()).isNotEqualTo(a.key());
            assertThat(otherStage.key()).isNotEqualTo(a.key());
            assertThat(otherPeriod.key()).isNotEqualTo(a.key());
        }
    }

    @Test
    void aClaimEndsExactlyOnce() {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        a.complete();
        assertThatThrownBy(a::complete).isInstanceOf(IllegalStateException.class);
        a.close(); // closing after completing is a no-op

        Claim b = acquire(freshKey(), "B");
        b.close();
        b.close(); // idempotent
        assertThatThrownBy(b::complete).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void badArgumentsAreRejected() {
        StageKey key = freshKey();
        assertThatThrownBy(() -> stageClaim().tryClaim(null, "A", Duration.ZERO))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> stageClaim().tryClaim(key, " ", Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> stageClaim().tryClaim(key, "A", Duration.ofMillis(-1)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new StageKey("u", "", "p")).isInstanceOf(IllegalArgumentException.class);
    }
}
