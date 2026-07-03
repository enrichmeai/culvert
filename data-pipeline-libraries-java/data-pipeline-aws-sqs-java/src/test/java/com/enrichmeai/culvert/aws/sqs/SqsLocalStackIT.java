package com.enrichmeai.culvert.aws.sqs;

import org.junit.jupiter.api.AfterAll;
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
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.CreateQueueRequest;
import software.amazon.awssdk.services.sqs.model.CreateQueueResponse;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for {@link SqsSource} and {@link SqsSink} exercised
 * against a real SQS API via Testcontainers'
 * {@link org.testcontainers.containers.localstack.LocalStackContainer}
 * (SQS has no dedicated Testcontainers module the way Pub/Sub does via
 * {@code PubSubEmulatorContainer}; LocalStack is the standard stand-in for
 * AWS services in this ecosystem).
 *
 * <p>Mirrors {@code PubSubSourceIT} / {@code PubSubSinkIT}'s shape: stands
 * up a real queue on the container, drives the adapters under test
 * end-to-end (send via {@link SqsSink}, read back via {@link SqsSource}),
 * and asserts the payloads round-trip. Both the sink and the source under
 * test share a single {@link SqsClient} pointed at the LocalStack endpoint.
 *
 * <p>{@link SqsSource#read} performs a single synchronous receive and
 * deletes eagerly whatever it returns (at-most-once, per the class
 * Javadoc), so it is driven in a short bounded loop here — same pattern as
 * {@code PubSubSourceIT}'s {@code readBodies} helper — to tolerate
 * LocalStack's SQS not always returning every in-flight message on the
 * first receive.
 *
 * <p><strong>Not run as part of the default build.</strong> Runs only under
 * the parent's {@code it} profile ({@code mvn -P it verify}) via failsafe,
 * and requires a running Docker daemon.
 *
 * <p>Sprint-21 deliverable (T21.3, epic #144).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class SqsLocalStackIT {

    private static final DockerImageName LOCALSTACK_IMAGE =
            DockerImageName.parse("localstack/localstack:3.4.0");

    private static final String QUEUE_NAME = "sqs-it-queue";

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(LOCALSTACK_IMAGE)
                    .withServices(LocalStackContainer.Service.SQS);

    private SqsClient client;
    private String queueUrl;
    private SqsSink sink;
    private SqsSource source;

    @BeforeAll
    void setUp() {
        client = SqsClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(LocalStackContainer.Service.SQS))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(
                                LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();

        CreateQueueResponse createResponse =
                client.createQueue(CreateQueueRequest.builder().queueName(QUEUE_NAME).build());
        queueUrl = createResponse.queueUrl();

        // Sink and source share the one client; each also implements
        // AutoCloseable and would close it — so only one of the two closes
        // it in tearDown to avoid a double-close.
        sink = new SqsSink(client, queueUrl);
        source = new SqsSource(client, queueUrl, 10, 1);
    }

    @AfterAll
    void tearDown() {
        // Only close once: both SqsSink#close and SqsSource#close delegate
        // to the same wrapped SqsClient.
        if (source != null) {
            source.close();
        }
    }

    /**
     * Drive the source's single-receive {@code read} repeatedly until
     * {@code want} payloads have been collected or the bounded attempts run
     * out. The source deletes what each receive returns, so re-reads only
     * surface not-yet-received messages.
     */
    private List<String> readBodies(int want) {
        List<String> bodies = new ArrayList<>();
        for (int attempt = 0; attempt < 20 && bodies.size() < want; attempt++) {
            Iterator<software.amazon.awssdk.services.sqs.model.Message> it = source.read(null);
            it.forEachRemaining(m -> bodies.add(m.body()));
        }
        return bodies;
    }

    @Test
    void queueUrlReflectsWiredAdapters() {
        assertThat(sink.queueUrl()).isEqualTo(queueUrl);
        assertThat(source.queueUrl()).isEqualTo(queueUrl);
    }

    @Test
    void writeThenReadRoundTripsMessagesThroughRealSqsApi() {
        sink.write(List.of("one", "two", "three").iterator(), null);

        List<String> bodies = readBodies(3);
        assertThat(bodies).containsExactlyInAnyOrder("one", "two", "three");

        // The source deletes eagerly, so a follow-up read sees nothing more.
        assertThat(source.read(null).hasNext()).isFalse();
    }

    @Test
    void writeBatchLargerThanSqsLimitRoundTripsAllMessages() {
        // 15 records exceeds SQS's 10-per-call batch limit, exercising
        // SqsSink's partitioning into multiple sendMessageBatch calls.
        List<String> sent = new ArrayList<>();
        for (int i = 0; i < 15; i++) {
            sent.add("bulk-" + i);
        }
        sink.write(sent.iterator(), null);

        List<String> received = readBodies(15);
        assertThat(received).containsExactlyInAnyOrderElementsOf(sent);
    }
}
