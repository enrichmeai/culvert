package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.aws.dynamodb.DynamoDbJobControlRepository;
import com.enrichmeai.culvert.aws.s3.S3BlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
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
import software.amazon.awssdk.services.dynamodb.model.CreateTableRequest;
import software.amazon.awssdk.services.dynamodb.model.KeySchemaElement;
import software.amazon.awssdk.services.dynamodb.model.KeyType;
import software.amazon.awssdk.services.dynamodb.model.ScalarAttributeType;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CreateBucketRequest;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.DYNAMODB;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.S3;

/**
 * <strong>The cloud-agnostic thesis, executed:</strong> the exact same
 * {@link IngestionRunner} that the GCP deployment runs (GCS + BigQuery +
 * BigQuery job control) is wired here with the AWS adapter family —
 * <em>real</em> {@link S3BlobStore} and <em>real</em>
 * {@link DynamoDbJobControlRepository} against LocalStack — and produces the
 * same result. Zero business-logic changes; only the adapter constructors
 * differ (exactly what {@code IngestionMain --cloud=aws} does).
 *
 * <p><strong>Honest scope:</strong> the {@code Warehouse} leg uses a
 * {@link RecordingWarehouse} because community LocalStack has no Athena
 * emulation. {@code AthenaWarehouse}'s load path (external table + typed
 * INSERT + COUNT + DROP, NDJSON and CSV) is covered by its own mocked-client
 * suite; real-AWS validation of that leg happens in the cloud deploy phase.
 *
 * <p>Runs only under {@code mvn -P it verify} (Docker required).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class CrossCloudIngestionLocalStackIT {

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(DockerImageName.parse("localstack/localstack:3.4.0"))
                    .withServices(S3, DYNAMODB);

    private static final String BUCKET = "cross-cloud-it";
    private static final String JOB_TABLE = "job_control_cross_cloud_it";
    private static final String SOURCE_URI =
            "s3://" + BUCKET + "/landing/generic/customers/generic_customers_20260601.csv";
    private static final String STAGING_PREFIX = "s3://" + BUCKET + "/staging";
    private static final String ERROR_PREFIX = "s3://" + BUCKET + "/errors";
    private static final String CSV_HEADER =
            "customer_id,first_name,last_name,ssn,dob,status,created_date";

    private S3Client s3;
    private S3BlobStore blobStore;
    private DynamoDbJobControlRepository jobControl;
    private RecordingWarehouse warehouse;

    @BeforeAll
    void setUp() {
        s3 = S3Client.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(S3))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .forcePathStyle(true)
                .build();
        s3.createBucket(CreateBucketRequest.builder().bucket(BUCKET).build());

        DynamoDbClient dynamo = DynamoDbClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(DYNAMODB))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();
        dynamo.createTable(CreateTableRequest.builder()
                .tableName(JOB_TABLE)
                .attributeDefinitions(AttributeDefinition.builder()
                        .attributeName("run_id").attributeType(ScalarAttributeType.S).build())
                .keySchema(KeySchemaElement.builder()
                        .attributeName("run_id").keyType(KeyType.HASH).build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .build());

        blobStore = new S3BlobStore(s3);
        jobControl = new DynamoDbJobControlRepository(dynamo, JOB_TABLE);
        warehouse = new RecordingWarehouse();
    }

    @Test
    void sameIngestionRunnerRunsAgainstAwsAdapters() {
        // Seed the HDR/TRL source file into REAL S3 through the adapter itself.
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                "cust-2,Alan,Turing,987-65-4321,1985-06-23,A,2019-05-05");
        blobStore.put(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260601", CSV_HEADER, rows));
        warehouse.returnRowCount(2);

        // The SAME runner class the GCP path uses — only the adapters differ.
        IngestionRunner runner = new IngestionRunner(
                blobStore, warehouse, jobControl, STAGING_PREFIX, ERROR_PREFIX);
        IngestionResult result = runner.run(new IngestionRequest(
                "aws-run-1", "customers", SOURCE_URI, "20260601", "odp.customers"));

        // Business outcome identical to the GCP-shaped runs.
        assertThat(result.candidateRowCount()).isEqualTo(2);
        assertThat(result.validRowCount()).isEqualTo(2);
        assertThat(result.loadedRowCount()).isEqualTo(2);
        assertThat(result.reconciliation().isReconciled()).isTrue();

        // Staged NDJSON really landed in S3 (read back through the adapter).
        String stagingUri = warehouse.loadCalls.get(0).uri();
        assertThat(stagingUri).startsWith(STAGING_PREFIX + "/customers/aws-run-1");
        assertThat(blobStore.exists(stagingUri)).isTrue();
        assertThat(new String(blobStore.get(stagingUri), java.nio.charset.StandardCharsets.UTF_8))
                .contains("\"customer_id\":\"cust-1\"");

        // Job control really transitioned in DynamoDB (conditional writes and all).
        assertThat(jobControl.getJob("aws-run-1"))
                .isPresent()
                .get()
                .satisfies(job -> assertThat(job.status()).isEqualTo(JobStatus.SUCCEEDED));
    }
}
