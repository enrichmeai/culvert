package com.enrichmeai.culvert.stageclaim;

/**
 * A held claim: while it is open, no other claimant can acquire the same {@link StageKey}.
 *
 * <p>End it exactly one way. {@link #complete()} records the stage as done, so every later claim on
 * the key reads {@link ClaimResult.Completed}. {@link #close()} without completing abandons it: the
 * stage was not done and the next claimant acquires it. Use try-with-resources so a failure inside
 * the stage abandons rather than leaks the claim.
 */
public interface Claim extends AutoCloseable {

    /** The stage this claim holds. */
    StageKey key();

    /** Who holds it, as given to {@code tryClaim}. */
    String claimant();

    /**
     * Records the stage as done and releases the claim.
     *
     * @throws IllegalStateException if the claim was already completed or closed
     */
    void complete();

    /** Releases the claim. If it was not completed, the stage stays not done. Idempotent. */
    @Override
    void close();
}
