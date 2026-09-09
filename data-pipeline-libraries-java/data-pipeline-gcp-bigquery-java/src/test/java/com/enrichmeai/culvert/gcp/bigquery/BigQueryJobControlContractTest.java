package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracttests.JobControlRepositoryContractTest;
import org.junit.jupiter.api.BeforeEach;

/**
 * Contract-test wiring for {@link BigQueryJobControlRepository}.
 *
 * <p>Runs the shared {@link JobControlRepositoryContractTest} — the spec all
 * three backends are held to — against the BigQuery implementation, driven
 * through {@link InMemoryBigQueryLedger}. That fixture is the reason this is
 * worth anything: it ranks its rows with the comparator it parses out of the
 * repository's own {@code ORDER BY}, so an inherited test passes because the
 * BigQuery projection ranks correctly, not because a mock was told what to
 * return.
 *
 * <p>No credentials and no network: the fixture is the whole backend.
 */
class BigQueryJobControlContractTest extends JobControlRepositoryContractTest {

    private static final String PROJECT = "contract-project";
    private static final String DATASET = "job_control";
    private static final String TABLE = "pipeline_jobs";

    private InMemoryBigQueryLedger ledger;
    private BigQueryJobControlRepository repository;

    @BeforeEach
    void setUp() throws InterruptedException {
        // One ledger per test method (JUnit's per-method lifecycle), so every
        // contract test starts from an empty store as the base class requires.
        ledger = new InMemoryBigQueryLedger();
        repository = new BigQueryJobControlRepository(
                ledger.client(), PROJECT, DATASET, TABLE);
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
