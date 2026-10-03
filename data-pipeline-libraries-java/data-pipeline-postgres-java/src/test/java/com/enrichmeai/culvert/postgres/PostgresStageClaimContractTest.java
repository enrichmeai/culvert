package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.contracttests.StageClaimContractTest;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.BeforeEach;

import javax.sql.DataSource;
import java.util.UUID;

/**
 * The shared {@link StageClaimContractTest} against {@link PostgresStageClaim} on a real PostgreSQL
 * server (embedded binaries, no Docker). Each {@code tryClaim} takes its own connection from an
 * unpooled data source, so claimants A and B are two server sessions. Those sessions carry a
 * per-test application name, which is how {@link #awaitWaiting} finds B waiting on the lock in
 * {@code pg_stat_activity} without mistaking any other session for it.
 */
class PostgresStageClaimContractTest extends StageClaimContractTest {

    private final String applicationName = "stageclaim-contract-" + UUID.randomUUID();
    private DataSource db;
    private StageClaim claim;

    @BeforeEach
    void setUp() {
        db = EmbeddedPostgresLedger.freshLedger();
        claim = new PostgresStageClaim(EmbeddedPostgresLedger.tagged(db, applicationName));
    }

    @Override
    protected void awaitWaiting(StageKey key) {
        EmbeddedPostgresLedger.awaitLockWait(db, applicationName);
    }

    @Override
    protected StageClaim stageClaim() {
        return claim;
    }
}
