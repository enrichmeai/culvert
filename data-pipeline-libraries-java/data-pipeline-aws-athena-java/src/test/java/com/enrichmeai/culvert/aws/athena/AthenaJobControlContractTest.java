package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracttests.JobControlRepositoryContractTest;
import org.junit.jupiter.api.BeforeEach;

/**
 * Contract-test wiring for {@link AthenaJobControlRepository}.
 *
 * <p>This is the artifact the external review's finding #4 asked for. The review
 * argued that job control's {@code UPDATE … SET status} "blocks Athena
 * entirely"; the append-only rebuild (AD-2/AD-3) was meant to unblock it, and
 * AD-13 required Athena to be built rather than merely declared possible.
 * Running the shared {@link JobControlRepositoryContractTest} — the spec all
 * backends are held to — against an Athena-backed repository is what turns that
 * argument into something falsifiable.
 *
 * <p>Driven through {@link InMemoryAthenaLedger}, which is the reason this is
 * worth anything: that fixture ranks its rows with the comparator and retry
 * epoch it parses out of the repository's own SQL, so an inherited test passes
 * because the Athena projection ranks correctly, not because a mock was told
 * what to return.
 *
 * <p>No credentials and no network: the fixture is the whole backend. Mirrors
 * the mocked-{@code AthenaClient} wiring of {@link AthenaWarehouseContractTest},
 * except that the client here is stateful — the base class calls
 * {@link #repository()} several times per test and every call must see the same
 * ledger.
 */
class AthenaJobControlContractTest extends JobControlRepositoryContractTest {

    private static final String DATABASE = "job_control";
    private static final String TABLE = "pipeline_jobs";
    private static final String OUTPUT_LOCATION = "s3://contract-bucket/athena-results/";

    private InMemoryAthenaLedger ledger;
    private AthenaJobControlRepository repository;

    @BeforeEach
    void setUp() {
        // One ledger per test method (JUnit's per-method lifecycle), so every
        // contract test starts from an empty store as the base class requires.
        ledger = new InMemoryAthenaLedger();
        repository = new AthenaJobControlRepository(
                ledger.client(), DATABASE, TABLE, OUTPUT_LOCATION);
    }

    @Override
    protected JobControlRepository repository() {
        return repository;
    }

    /**
     * Writes straight to the ledger, around the transition guard, so the base
     * suite can test the projection in isolation rather than trusting the
     * guard to have caught the contradiction first.
     */
    @Override
    protected void appendRaw(String runId, com.enrichmeai.culvert.jobcontrol.JobStatus status) {
        ledger.appendRaw(runId, status);
    }
}
