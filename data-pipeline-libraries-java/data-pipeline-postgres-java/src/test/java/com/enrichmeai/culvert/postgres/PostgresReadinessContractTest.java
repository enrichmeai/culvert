package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.contracttests.InputReadinessContractTest;
import org.junit.jupiter.api.BeforeEach;

/**
 * The shared {@link InputReadinessContractTest} against {@link PostgresReadiness} on a real
 * PostgreSQL server (embedded binaries, no Docker).
 */
class PostgresReadinessContractTest extends InputReadinessContractTest {

    private InputReadiness readiness;

    @BeforeEach
    void setUp() {
        readiness = new PostgresReadiness(EmbeddedPostgresLedger.freshLedger());
    }

    @Override
    protected InputReadiness readiness() {
        return readiness;
    }
}
