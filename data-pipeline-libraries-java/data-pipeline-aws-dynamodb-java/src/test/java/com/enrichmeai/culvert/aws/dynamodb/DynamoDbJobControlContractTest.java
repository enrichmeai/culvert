package com.enrichmeai.culvert.aws.dynamodb;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracttests.JobControlRepositoryContractTest;
import com.enrichmeai.culvert.jobcontrol.JobStatus;

/**
 * Contract-test wiring for {@link DynamoDbJobControlRepository}.
 *
 * <p>Runs the shared {@link JobControlRepositoryContractTest} — the suite that
 * turns "append-only job control is implementable on a store with no
 * {@code UPDATE}" from an argument into something falsifiable — against a
 * DynamoDB-shaped ledger held in {@link InMemoryDynamoDb}.
 *
 * <p>One repository and one ledger per test method (JUnit's default per-method
 * lifecycle), so every {@code runId} the suite mints starts empty, and
 * {@code repository()} keeps returning the same store within a test — which the
 * suite relies on, since it appends through one call and reads back through
 * another.
 *
 * <p>The fake, not a mock: a mocked client would return whatever the test told
 * it to and could not tell a correct projection from a broken one. See
 * {@link InMemoryDynamoDb} for what it models and what it refuses.
 *
 * <p>Sprint-23 deliverable (AD-12/AD-13). Mirrors {@code S3BlobStoreContractTest}
 * in {@code data-pipeline-aws-s3-java}.
 */
class DynamoDbJobControlContractTest extends JobControlRepositoryContractTest {

    private static final String TABLE = "job_control";

    private final InMemoryDynamoDb client = new InMemoryDynamoDb();
    private final DynamoDbJobControlRepository repository =
            new DynamoDbJobControlRepository(client, TABLE);

    @Override
    protected JobControlRepository repository() {
        return repository;
    }

    /**
     * Writes an item straight into the ledger, past the repository and its
     * transition guard, at a sort key later than every generated one.
     *
     * <p>This is what makes
     * {@code theProjectionItselfKeepsTheEarliestTerminalState} test the
     * projection rather than the guard: driven through {@link #repository()},
     * a late {@code markFailed} on a succeeded run is rejected before the fold
     * is ever consulted, so the suite would stay green over a projection that
     * had degenerated to last-write-wins. It is also not a contrivance —
     * read-then-append is deliberately not atomic, so a racing writer or a
     * redelivered event lands exactly this item.
     */
    @Override
    protected void appendRaw(String runId, JobStatus status) {
        client.appendRaw(TABLE, runId, status.getValue(), null);
    }
}
