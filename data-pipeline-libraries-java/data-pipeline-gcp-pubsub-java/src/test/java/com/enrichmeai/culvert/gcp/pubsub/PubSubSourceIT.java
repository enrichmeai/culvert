package com.enrichmeai.culvert.gcp.pubsub;

import com.google.api.gax.core.CredentialsProvider;
import com.google.api.gax.core.NoCredentialsProvider;
import com.google.api.gax.grpc.GrpcTransportChannel;
import com.google.api.gax.rpc.FixedTransportChannelProvider;
import com.google.api.gax.rpc.TransportChannelProvider;
import com.google.cloud.pubsub.v1.Publisher;
import com.google.cloud.pubsub.v1.SubscriptionAdminClient;
import com.google.cloud.pubsub.v1.SubscriptionAdminSettings;
import com.google.cloud.pubsub.v1.TopicAdminClient;
import com.google.cloud.pubsub.v1.TopicAdminSettings;
import com.google.cloud.pubsub.v1.stub.GrpcSubscriberStub;
import com.google.cloud.pubsub.v1.stub.SubscriberStub;
import com.google.cloud.pubsub.v1.stub.SubscriberStubSettings;
import com.google.protobuf.ByteString;
import com.google.pubsub.v1.PubsubMessage;
import com.google.pubsub.v1.PushConfig;
import com.google.pubsub.v1.SubscriptionName;
import com.google.pubsub.v1.TopicName;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.containers.PubSubEmulatorContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for {@link PubSubSource} exercised against a real Pub/Sub
 * emulator via Testcontainers' built-in
 * {@link org.testcontainers.containers.PubSubEmulatorContainer} (gcloud
 * module).
 *
 * <p>Where {@code PubSubSourceTest} mocks the {@link SubscriberStub} and
 * asserts on the pull/ack calls the adapter issues, this IT drives the source
 * end-to-end: it stands up a topic + subscription on the emulator, publishes
 * messages with a raw SDK {@link Publisher} (NOT the adapter), then reads them
 * back through the {@link PubSubSource} under test (its {@link SubscriberStub}
 * wired at the emulator endpoint via a {@link TransportChannelProvider} +
 * {@link NoCredentialsProvider}) and asserts the payloads round-trip. Keeping
 * the publish side on the raw SDK isolates the failure surface to
 * {@link PubSubSource}.
 *
 * <p>Ordering is load-bearing: the topic and subscription are created BEFORE
 * any publish, because Pub/Sub drops messages published before a subscription
 * exists. {@link PubSubSource#read} issues a single synchronous pull and acks
 * only what it returns, so it is driven in a short bounded loop to collect the
 * expected messages without flakiness.
 *
 * <p>Sprint-10 deliverable (T10.3).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class PubSubSourceIT {

    /**
     * Cloud SDK image carrying the Pub/Sub emulator. The gcloud module's
     * {@link PubSubEmulatorContainer} has no no-arg constructor, so the image
     * is supplied explicitly.
     */
    private static final DockerImageName EMULATOR_IMAGE =
            DockerImageName.parse("gcr.io/google.com/cloudsdktool/cloud-sdk:emulators");

    private static final String PROJECT_ID = "culvert-it-project";
    private static final String TOPIC_ID = "source-it-topic";
    private static final String SUBSCRIPTION_ID = "source-it-subscription";
    private static final int ACK_DEADLINE_SECONDS = 10;

    @Container
    static final PubSubEmulatorContainer EMULATOR =
            new PubSubEmulatorContainer(EMULATOR_IMAGE);

    private static final TopicName TOPIC_NAME =
            TopicName.of(PROJECT_ID, TOPIC_ID);
    private static final SubscriptionName SUBSCRIPTION_NAME =
            SubscriptionName.of(PROJECT_ID, SUBSCRIPTION_ID);

    private ManagedChannel channel;
    private TransportChannelProvider channelProvider;
    private CredentialsProvider credentialsProvider;

    private Publisher publisher;
    private PubSubSource source;

    @BeforeAll
    void setUp() throws IOException {
        // Single plaintext channel at the emulator endpoint, reused by every
        // client. NoCredentials because the emulator does not authenticate.
        channel = ManagedChannelBuilder
                .forTarget(EMULATOR.getEmulatorEndpoint())
                .usePlaintext()
                .build();
        channelProvider = FixedTransportChannelProvider.create(
                GrpcTransportChannel.create(channel));
        credentialsProvider = NoCredentialsProvider.create();

        // Order matters: create topic, THEN subscription, BEFORE publishing.
        try (TopicAdminClient topicAdmin = TopicAdminClient.create(
                TopicAdminSettings.newBuilder()
                        .setTransportChannelProvider(channelProvider)
                        .setCredentialsProvider(credentialsProvider)
                        .build())) {
            topicAdmin.createTopic(TOPIC_NAME);
        }
        try (SubscriptionAdminClient subscriptionAdmin = SubscriptionAdminClient.create(
                SubscriptionAdminSettings.newBuilder()
                        .setTransportChannelProvider(channelProvider)
                        .setCredentialsProvider(credentialsProvider)
                        .build())) {
            subscriptionAdmin.createSubscription(SUBSCRIPTION_NAME, TOPIC_NAME,
                    PushConfig.getDefaultInstance(), ACK_DEADLINE_SECONDS);
        }

        // Raw SDK publisher for seeding (not the adapter).
        publisher = Publisher.newBuilder(TOPIC_NAME)
                .setChannelProvider(channelProvider)
                .setCredentialsProvider(credentialsProvider)
                .build();

        // Subscriber stub wired at the emulator endpoint, wrapped by the
        // source under test. The source owns and closes this stub.
        SubscriberStub stub = GrpcSubscriberStub.create(
                SubscriberStubSettings.newBuilder()
                        .setTransportChannelProvider(channelProvider)
                        .setCredentialsProvider(credentialsProvider)
                        .build());
        source = new PubSubSource(stub, SUBSCRIPTION_NAME.toString());
    }

    @AfterAll
    void tearDown() throws InterruptedException {
        // PubSubSource#close() closes the wrapped SubscriberStub.
        if (source != null) {
            source.close();
        }
        if (publisher != null) {
            publisher.shutdown();
            publisher.awaitTermination(10L, TimeUnit.SECONDS);
        }
        if (channel != null) {
            channel.shutdownNow();
        }
    }

    private static PubsubMessage msg(String body) {
        return PubsubMessage.newBuilder()
                .setData(ByteString.copyFromUtf8(body))
                .build();
    }

    /** Publish one message via the raw SDK publisher and block on its id. */
    private void publish(String body) throws InterruptedException, ExecutionException {
        // get() resolves the publish future so the message is durably accepted
        // by the emulator before we attempt to read it back.
        publisher.publish(msg(body)).get();
    }

    /**
     * Drive the source's single-pull {@code read} repeatedly until {@code want}
     * payloads have been collected or the bounded attempts run out. The source
     * acks what each pull returns, so re-reads only surface not-yet-pulled
     * messages.
     */
    private List<String> readBodies(int want) throws InterruptedException {
        List<String> bodies = new ArrayList<>();
        for (int attempt = 0; attempt < 20 && bodies.size() < want; attempt++) {
            Iterator<PubsubMessage> it = source.read(null);
            if (!it.hasNext()) {
                Thread.sleep(200L);
                continue;
            }
            it.forEachRemaining(m -> bodies.add(m.getData().toStringUtf8()));
        }
        return bodies;
    }

    @Test
    void subscriptionNameReflectsWiredSource() {
        assertThat(source.subscriptionName()).isEqualTo(SUBSCRIPTION_NAME.toString());
    }

    @Test
    void readPullsAndAcksMessagesPublishedToTheTopic()
            throws InterruptedException, ExecutionException {
        // Seed via the raw SDK publisher.
        publish("one");
        publish("two");
        publish("three");

        // Read them back through the adapter under test.
        List<String> bodies = readBodies(3);
        assertThat(bodies).containsExactlyInAnyOrder("one", "two", "three");

        // The source acks eagerly, so a follow-up read sees nothing more.
        assertThat(source.read(null).hasNext()).isFalse();
    }
}
