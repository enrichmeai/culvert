package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;

import java.time.Duration;

/**
 * Atomic claim on one stage of one unit for one period: <strong>a stage cannot double-start, and an
 * interrupted stage is picked up again by the next claimant.</strong> Control-plane epic #188.
 *
 * <h2>An optional capability</h2>
 * <p>Only a backend that can lock implements it (today: PostgreSQL). BigQuery, Athena and DynamoDB
 * job control do not, so on those deployments {@code AutoConfig.stageClaim()} is empty and the
 * caller decides what that means: run unguarded, or refuse to run. It is a separate port, not a
 * {@link JobControlRepository} method, because a claim is keyed by {@link StageKey}, not a
 * {@code runId}, and because two of the job-control backends cannot hold a lock.
 *
 * <h2>The guarantee</h2>
 * <ul>
 *   <li>At most one claimant holds a key at a time.
 *   <li>Once a holder calls {@link Claim#complete()}, every later claim on the key returns
 *       {@link ClaimResult.Completed}: the stage never runs twice.
 *   <li>If the holder abandons the claim ({@link Claim#close()} without completing) or dies, the
 *       stage is not done and the next claimant acquires it.
 * </ul>
 * <p>How a dead holder's claim is released is the backend's to state; see its documentation.
 *
 * <p>Java only for now: the Python mirror is #196, waiting on decision A in #188.
 */
public interface StageClaim {

    /**
     * Try to claim {@code key} for {@code claimant}, waiting up to {@code maxWait} for a current
     * holder to finish. {@link Duration#ZERO} does not wait.
     *
     * <p>If the holder completes while this call waits, the result is {@link ClaimResult.Completed};
     * if it abandons, the result is {@link ClaimResult.Acquired}; if it still holds when
     * {@code maxWait} runs out, {@link ClaimResult.Held}.
     *
     * @throws IllegalArgumentException if {@code claimant} is blank or {@code maxWait} is negative
     */
    ClaimResult tryClaim(StageKey key, String claimant, Duration maxWait);
}
