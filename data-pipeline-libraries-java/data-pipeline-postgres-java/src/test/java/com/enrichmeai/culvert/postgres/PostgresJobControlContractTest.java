package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracttests.JobControlRepositoryContractTest;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import org.junit.jupiter.api.BeforeEach;

import javax.sql.DataSource;

/**
 * Runs the shared {@link JobControlRepositoryContractTest}, unchanged, against
 * {@link PostgresJobControlRepository} on a real PostgreSQL server (embedded binaries, no Docker).
 * The projection is PostgreSQL's own window function over the shipped DDL, so an inherited test
 * passes because the SQL ranks correctly, not because a fake was told what to return.
 */
class PostgresJobControlContractTest extends JobControlRepositoryContractTest {

    private DataSource db;
    private PostgresJobControlRepository repository;

    @BeforeEach
    void setUp() {
        db = EmbeddedPostgresLedger.freshLedger();
        repository = new PostgresJobControlRepository(db);
    }

    @Override
    protected JobControlRepository repository() {
        return repository;
    }

    @Override
    protected void appendRaw(String runId, JobStatus status) {
        EmbeddedPostgresLedger.appendRaw(db, runId, status);
    }
}
