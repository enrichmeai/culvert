package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

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
 * <p>The wake-up cases (B is waiting, then A completes or abandons) need B on a second thread. They
 * stay deterministic because {@link #awaitWaiting(StageKey)} reports, from the backend's own
 * state, that B is waiting before A moves. The order is fixed, not timed.
 *
 * <p>Subclasses provide {@link #stageClaim()} and {@link #awaitWaiting(StageKey)}. Each
 * {@code tryClaim} call must be an independent
 * claimant (a separate session, connection or lock owner), even from the same thread. An
 * implementation whose lock is re-entrant per thread would let B acquire what A holds, and fails here.
 */
public abstract class StageClaimContractTest {

    /** The claim under test. Keys are fresh per test, so state may persist between tests. */
    protected abstract StageClaim stageClaim();

    /**
     * Return once a claimant is waiting on {@code key}: a {@code tryClaim} with a wait that is
     * blocked on the current holder. Read the backend's own state (a lock queue, the server's
     * session list), and never sleep and hope.
     *
     * <p>The default <strong>fails</strong>: a backend that cannot show a claimant waiting cannot
     * prove the wake-up guarantees, and must not pass this suite on the strength of the others.
     */
    protected void awaitWaiting(StageKey key) {
        throw new AssertionError(getClass().getSimpleName() + " must override awaitWaiting(key), "
                + "so the wake-up cases are ordered by the backend's state rather than by a sleep");
    }

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
    void aWaitingClaimantWakesToCompletedWhenTheHolderCompletes() throws Exception {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        ExecutorService second = Executors.newSingleThreadExecutor();
        try {
            Future<ClaimResult> b = second.submit(() -> stageClaim().tryClaim(key, "B", Duration.ofSeconds(30)));
            awaitWaiting(key);
            assertThat(b).as("B is still waiting on A").isNotDone();

            a.complete();

            ClaimResult result = b.get(10, TimeUnit.SECONDS);
            assertThat(result).isInstanceOf(ClaimResult.Completed.class);
            assertThat(((ClaimResult.Completed) result).completedBy()).isEqualTo("A");
        } finally {
            a.close();
            second.shutdownNow();
        }
    }

    @Test
    void aWaitingClaimantWakesToAcquiredWhenTheHolderAbandons() throws Exception {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        ExecutorService second = Executors.newSingleThreadExecutor();
        try {
            Future<ClaimResult> b = second.submit(() -> stageClaim().tryClaim(key, "B", Duration.ofSeconds(30)));
            awaitWaiting(key);
            assertThat(b).isNotDone();

            a.close();

            ClaimResult result = b.get(10, TimeUnit.SECONDS);
            assertThat(result).isInstanceOf(ClaimResult.Acquired.class);
            try (Claim claimB = ((ClaimResult.Acquired) result).claim()) {
                assertThat(claimB.claimant()).isEqualTo("B");
            }
        } finally {
            second.shutdownNow();
        }
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
    void completionIsEmptyUntilTheStageCompletesAndThenNamesTheHolder() {
        StageKey key = freshKey();
        assertThat(stageClaim().completion(key)).as("never claimed").isEmpty();

        try (Claim a = acquire(key, "A")) {
            assertThat(stageClaim().completion(key)).as("held, not completed").isEmpty();
            a.complete();
        }
        ClaimResult.Completed done = stageClaim().completion(key).orElseThrow();
        assertThat(done.key()).isEqualTo(key);
        assertThat(done.completedBy()).isEqualTo("A");
        assertThat(stageClaim().tryClaim(key, "B", Duration.ZERO))
                .as("the read and a claim agree on the completion")
                .isEqualTo(done);
    }

    @Test
    void anAbandonedStageReadsAsNotCompleted() {
        StageKey key = freshKey();
        acquire(key, "A").close();
        assertThat(stageClaim().completion(key)).isEmpty();
    }

    @Test
    void readingACompletionNeverClaimsTheStage() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            assertThat(stageClaim().completion(key)).isEmpty();
            assertThat(a.claimant()).isEqualTo("A");
            assertThat(stageClaim().tryClaim(key, "B", Duration.ZERO))
                    .as("A still holds the stage after the read")
                    .isEqualTo(new ClaimResult.Held(key));
        }
        assertThat(stageClaim().completion(key)).isEmpty();
        try (Claim b = acquire(key, "B")) {
            assertThat(b.claimant()).as("the read left nothing held").isEqualTo("B");
        }
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
        assertThatThrownBy(() -> stageClaim().completion(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new StageKey("u", "", "p")).isInstanceOf(IllegalArgumentException.class);
    }
}
