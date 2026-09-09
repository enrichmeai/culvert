package com.enrichmeai.culvert.aws.dynamodb;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.containers.localstack.LocalStackContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeDefinition;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BillingMode;
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.CreateTableRequest;
import software.amazon.awssdk.services.dynamodb.model.KeySchemaElement;
import software.amazon.awssdk.services.dynamodb.model.KeyType;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.ScalarAttributeType;

import java.time.LocalDate;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.DYNAMODB;

/**
 * Integration tests for {@link DynamoDbJobControlRepository} against real
 * DynamoDB API semantics (localstack/localstack) via Testcontainers.
 *
 * <p>Where the unit test mocks {@code DynamoDbClient} and asserts request
 * shapes, this IT creates a real table and proves the properties that only a
 * real server can settle: the {@code attribute_not_exists} guard at the
 * {@code created} sentinel really does reject a duplicate run atomically, an
 * append really does leave the earlier items in place, the projection really
 * does hold across a marshal/unmarshal round trip, and a terminal state really
 * is immutable. Suffixed {@code IT}; runs only under {@code mvn -P it verify}
 * (Docker required).
 *
 * <p>Sprint-21 deliverable (T21.4, issue #148); re-keyed onto the composite
 * {@code (run_id, event_seq)} schema in Sprint 23 when the adapter became
 * append-only (AD-2/AD-3/AD-13).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class DynamoDbJobControlLocalStackIT {

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(DockerImageName.parse("localstack/localstack:3.4.0"))
                    .withServices(DYNAMODB);

    private static final String TABLE = "job_control_it";

    private DynamoDbClient client;
    private DynamoDbJobControlRepository repo;

    @BeforeAll
    void setUp() {
        client = DynamoDbClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(DYNAMODB))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();
        // Composite key: one item per state change, ascending by event_seq.
        // A PK-only table cannot serve the append-only adapter.
        client.createTable(CreateTableRequest.builder()
                .tableName(TABLE)
                .attributeDefinitions(
                        AttributeDefinition.builder()
                                .attributeName(DynamoDbJobControlRepository.ATTR_RUN_ID)
                                .attributeType(ScalarAttributeType.S).build(),
                        AttributeDefinition.builder()
                                .attributeName(DynamoDbJobControlRepository.ATTR_EVENT_SEQ)
                                .attributeType(ScalarAttributeType.S).build())
                .keySchema(
                        KeySchemaElement.builder()
                                .attributeName(DynamoDbJobControlRepository.ATTR_RUN_ID)
                                .keyType(KeyType.HASH).build(),
                        KeySchemaElement.builder()
                                .attributeName(DynamoDbJobControlRepository.ATTR_EVENT_SEQ)
                                .keyType(KeyType.RANGE).build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .build());
        repo = new DynamoDbJobControlRepository(client, TABLE);
    }

    private static PipelineJob job(String runId) {
        return PipelineJob.builder(
                runId, "GENERIC", "ingest_customers",
                LocalDate.of(2026, 1, 15), JobStatus.CREATED).build();
    }

    /** How many items the ledger holds for one run — the append-only counter. */
    private int itemsFor(String runId) {
        return client.query(QueryRequest.builder()
                .tableName(TABLE)
                .keyConditionExpression("#run_id = :run_id")
                .expressionAttributeNames(Map.of("#run_id", DynamoDbJobControlRepository.ATTR_RUN_ID))
                .expressionAttributeValues(Map.of(":run_id", AttributeValue.fromS(runId)))
                .build()).items().size();
    }

    @Test
    void createThenGetRoundTrips() {
        repo.createJob(job("it-run-1"));

        Optional<PipelineJob> found = repo.getJob("it-run-1");
        assertThat(found).isPresent();
        assertThat(found.get().systemId()).isEqualTo("GENERIC");
        assertThat(found.get().status()).isEqualTo(JobStatus.CREATED);
        assertThat(found.get().extractDate()).isEqualTo(LocalDate.of(2026, 1, 15));
    }

    @Test
    void duplicateCreateIsRejectedAtomically() {
        repo.createJob(job("it-run-dup"));

        // The sentinel sort key is what keeps this atomic on a composite-key
        // table: both creates target the same item, so the server's condition
        // check decides, with no read-then-write window.
        assertThatThrownBy(() -> repo.createJob(job("it-run-dup")))
                .isInstanceOf(ConditionalCheckFailedException.class);
        assertThat(itemsFor("it-run-dup")).isEqualTo(1);
    }

    @Test
    void statusTransitionOnMissingRunIsRejected() {
        // No longer a server-side conditional check: append-only moved the
        // guard ahead of the write, so this is the adapter's own rejection.
        assertThatThrownBy(() -> repo.updateStatus("it-never-created", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=it-never-created");
        assertThat(itemsFor("it-never-created")).isZero();
    }

    @Test
    void everyStateChangeAppendsAndTheFailedRunStaysFailed() {
        repo.createJob(job("it-run-life"));
        repo.updateStatus("it-run-life", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("it-run-life", "E42", "boom", FailureStage.LOAD,
                Optional.of("s3://errors/it-run-life.json"));
        repo.markRetrying("it-run-life", 1);

        assertThat(itemsFor("it-run-life"))
                .as("four state changes, four items: nothing was updated in place")
                .isEqualTo(4);

        Optional<PipelineJob> found = repo.getJob("it-run-life");
        assertThat(found).isPresent();
        assertThat(found.get().status())
                .as("CONTRACT.md section 7: the retry is a new run; this one stays failed")
                .isEqualTo(JobStatus.FAILED);
        assertThat(found.get().errorCode()).contains("E42");
    }

    @Test
    void aTerminalStateSurvivesALaterContradictingCall() {
        repo.createJob(job("it-run-done"));
        repo.updateStatus("it-run-done", JobStatus.RUNNING, Optional.empty());
        repo.updateStatus("it-run-done", JobStatus.SUCCEEDED, Optional.of(3L));

        assertThatThrownBy(() -> repo.markFailed("it-run-done", "LATE", "arrived late",
                FailureStage.UNKNOWN, Optional.empty()))
                .isInstanceOf(IllegalStateException.class);

        assertThat(repo.getJob("it-run-done")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.SUCCEEDED);
    }

    @Test
    void pendingJobsFindsCreatedRuns() {
        repo.createJob(job("it-run-pending"));

        assertThat(repo.getPendingJobs(Optional.of("GENERIC")))
                .anyMatch(j -> j.runId().equals("it-run-pending"));
    }

    @Test
    void pendingJobsExcludesARunThatHasSinceSucceeded() {
        // The scan cannot filter on status any more; this proves the fold, and
        // not the FilterExpression, is what keeps a finished run out.
        repo.createJob(job("it-run-finished"));
        repo.updateStatus("it-run-finished", JobStatus.RUNNING, Optional.empty());
        repo.updateStatus("it-run-finished", JobStatus.SUCCEEDED, Optional.of(1L));

        assertThat(repo.getPendingJobs(Optional.of("GENERIC")))
                .noneMatch(j -> j.runId().equals("it-run-finished"));
    }

    @Test
    void costMetricsUpdateRoundTrips() {
        repo.createJob(job("it-run-cost"));
        repo.updateCostMetrics("it-run-cost", 1.25, 1024L, 2048L);

        Optional<PipelineJob> found = repo.getJob("it-run-cost");
        assertThat(found).isPresent();
        assertThat(found.get().billedBytesScanned()).isEqualTo(1024L);
        assertThat(found.get().billedBytesWritten()).isEqualTo(2048L);
    }
}
