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
import software.amazon.awssdk.services.dynamodb.model.BillingMode;
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.CreateTableRequest;
import software.amazon.awssdk.services.dynamodb.model.KeySchemaElement;
import software.amazon.awssdk.services.dynamodb.model.KeyType;
import software.amazon.awssdk.services.dynamodb.model.ScalarAttributeType;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.DYNAMODB;

/**
 * Integration tests for {@link DynamoDbJobControlRepository} against real
 * DynamoDB API semantics (localstack/localstack) via Testcontainers.
 *
 * <p>Where the unit test mocks {@code DynamoDbClient} and asserts request
 * shapes, this IT creates a real table and proves the <em>transactional</em>
 * properties end-to-end: the {@code attribute_not_exists} guard actually
 * rejects duplicate runs, the {@code attribute_exists} compare-and-swap
 * actually rejects transitions on missing runs, and full job round-trips
 * survive the marshal/unmarshal path. Suffixed {@code IT}; runs only under
 * {@code mvn -P it verify} (Docker required).
 *
 * <p>Sprint-21 deliverable (T21.4, issue #148) — added at architect
 * verification after the dev-agent's connection dropped pre-IT.
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class DynamoDbJobControlLocalStackIT {

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(DockerImageName.parse("localstack/localstack:3.4.0"))
                    .withServices(DYNAMODB);

    private static final String TABLE = "job_control_it";

    private DynamoDbJobControlRepository repo;

    @BeforeAll
    void setUp() {
        DynamoDbClient client = DynamoDbClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(DYNAMODB))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();
        client.createTable(CreateTableRequest.builder()
                .tableName(TABLE)
                .attributeDefinitions(AttributeDefinition.builder()
                        .attributeName(DynamoDbJobControlRepository.ATTR_RUN_ID)
                        .attributeType(ScalarAttributeType.S).build())
                .keySchema(KeySchemaElement.builder()
                        .attributeName(DynamoDbJobControlRepository.ATTR_RUN_ID)
                        .keyType(KeyType.HASH).build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .build());
        repo = new DynamoDbJobControlRepository(client, TABLE);
    }

    private static PipelineJob job(String runId) {
        return PipelineJob.builder(
                runId, "GENERIC", "ingest_customers",
                LocalDate.of(2026, 1, 15), JobStatus.CREATED).build();
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

        assertThatThrownBy(() -> repo.createJob(job("it-run-dup")))
                .isInstanceOf(ConditionalCheckFailedException.class);
    }

    @Test
    void statusTransitionOnMissingRunIsRejectedAtomically() {
        assertThatThrownBy(() -> repo.updateStatus("it-never-created", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(ConditionalCheckFailedException.class);
    }

    @Test
    void fullLifecycleCreateRunFailRetry() {
        repo.createJob(job("it-run-life"));
        repo.updateStatus("it-run-life", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("it-run-life", "E42", "boom", FailureStage.LOAD,
                Optional.of("s3://errors/it-run-life.json"));
        repo.markRetrying("it-run-life", 1);

        Optional<PipelineJob> found = repo.getJob("it-run-life");
        assertThat(found).isPresent();
        assertThat(found.get().status()).isEqualTo(JobStatus.RETRYING);
        assertThat(found.get().retryCount()).isEqualTo(1);
    }

    @Test
    void pendingJobsFindsCreatedRuns() {
        repo.createJob(job("it-run-pending"));

        assertThat(repo.getPendingJobs(Optional.of("GENERIC")))
                .anyMatch(j -> j.runId().equals("it-run-pending"));
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
