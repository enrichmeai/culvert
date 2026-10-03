package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/**
 * The reference: an in-memory {@link StageClaim} that passes {@link StageClaimContractTest}, so a
 * failure in a backend's run of the suite is the backend's, not the suite's. A {@link Semaphore} per
 * key, not a re-entrant lock, so a second claim from the same thread contends like a second session.
 */
class InMemoryStageClaimContractTest extends StageClaimContractTest {

    private final InMemoryStageClaim claim = new InMemoryStageClaim();

    @Override
    protected StageClaim stageClaim() {
        return claim;
    }

    static final class InMemoryStageClaim implements StageClaim {
        private final Map<StageKey, Semaphore> locks = new ConcurrentHashMap<>();
        private final Map<StageKey, ClaimResult.Completed> done = new ConcurrentHashMap<>();

        @Override
        public ClaimResult tryClaim(StageKey key, String claimant, Duration maxWait) {
            Objects.requireNonNull(key, "key must not be null");
            Objects.requireNonNull(claimant, "claimant must not be null");
            Objects.requireNonNull(maxWait, "maxWait must not be null");
            if (claimant.isBlank()) {
                throw new IllegalArgumentException("claimant must not be blank");
            }
            if (maxWait.isNegative()) {
                throw new IllegalArgumentException("maxWait must not be negative");
            }
            Semaphore lock = locks.computeIfAbsent(key, k -> new Semaphore(1));
            boolean got;
            try {
                got = lock.tryAcquire(maxWait.toNanos(), TimeUnit.NANOSECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return new ClaimResult.Held(key);
            }
            if (!got) {
                ClaimResult.Completed completed = done.get(key);
                return completed != null ? completed : new ClaimResult.Held(key);
            }
            ClaimResult.Completed completed = done.get(key);
            if (completed != null) {
                lock.release();
                return completed;
            }
            return new ClaimResult.Acquired(new Claim() {
                private boolean ended;

                @Override
                public StageKey key() {
                    return key;
                }

                @Override
                public String claimant() {
                    return claimant;
                }

                @Override
                public synchronized void complete() {
                    if (ended) {
                        throw new IllegalStateException("claim on " + key + " already ended");
                    }
                    done.put(key, new ClaimResult.Completed(key, claimant, Instant.now()));
                    ended = true;
                    lock.release();
                }

                @Override
                public synchronized void close() {
                    if (!ended) {
                        ended = true;
                        lock.release();
                    }
                }
            });
        }
    }
}
