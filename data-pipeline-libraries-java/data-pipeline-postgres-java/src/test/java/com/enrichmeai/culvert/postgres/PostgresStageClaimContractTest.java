package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.contracttests.StageClaimContractTest;
import org.junit.jupiter.api.BeforeEach;

/**
 * The shared {@link StageClaimContractTest} against {@link PostgresStageClaim} on a real PostgreSQL
 * server (embedded binaries, no Docker). Each {@code tryClaim} takes its own connection from an
 * unpooled data source, so claimants A and B are two server sessions.
 */
class PostgresStageClaimContractTest extends StageClaimContractTest {

    private StageClaim claim;

    @BeforeEach
    void setUp() {
        claim = new PostgresStageClaim(EmbeddedPostgresLedger.freshLedger());
    }

    @Override
    protected StageClaim stageClaim() {
        return claim;
    }
}
