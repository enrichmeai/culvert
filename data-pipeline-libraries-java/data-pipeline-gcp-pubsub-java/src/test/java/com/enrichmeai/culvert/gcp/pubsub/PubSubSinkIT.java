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
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * End-to-end round-trip integration test exercising BOTH Culvert Pub/Sub
 * adapters against a real Pub/Sub emulator via Testcontainers' built-in
 * {@link org.testcontainers.containers.PubSubEmulatorContainer} (gcloud
 * module): a message is published through {@link PubSubSink} and pulled back
 * through {@link PubSubSource}, satisfying the T10.3 "publish via PubSubSink,
 * pull via PubSubSource, assert the message round-trips" deliverable.
 *
 * <p>Where {@code PubSubSinkTest} mocks the {@link Publisher} and asserts on
 * the publish calls the adapter issues, this IT drives the sink end-to-end:
 * it stands up a topic + subscription on the emulator, publishes through the
 * {@link PubSubSink} under test (its {@link Publisher} wired at the emulator
 * endpoint via a {@link TransportChannelProvider} + {@link NoCredentialsProvider}),
 * then reads the messages back through a {@link PubSubSource} wired at the same
 * endpoint and asserts the payloads round-trip.
 *
 * <p>Ordering is load-bearing: the topic and subscription are created in
 * {@link #setUp()} BEFORE any publish, because Pub/Sub drops messages
 * published before a subscription exists. {@link PubSubSource#read} issues a
 * single synchronous pull and acks only what it returns, so it is driven in a
 * short bounded loop to collect the expected messages without flakiness.
 *
 * <p>Sprint-10 deliverable (T10.3).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class PubSubSinkIT {

    /**
     * Cloud SDK image carrying the Pub/Sub emulator. The gcloud module's
     * {@link PubSubEmulatorContainer} has no no-arg constructor, so the image
     * is supplied explicitly.
     */
    private static final DockerImageName EMULATOR_IMAGE =
            DockerImageName.parse("gcr.io/google.com/cloudsdktool/cloud-sdk:emulators");

    private static final String PROJECT_ID = "culvert-it-project";
    private static final String TOPIC_ID = "sink-it-topic";
    private static final String SUBSCRIPTION_ID = "sink-it-subscription";
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

    private PubSubSink sink;
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

        // Publisher wired at the emulator endpoint, wrapped by the sink under test.
        Publisher publisher = Publisher.newBuilder(TOPIC_NAME)
                .setChannelProvider(channelProvider)
                .setCredentialsProvider(credentialsProvider)
                .build();
        sink = new PubSubSink(publisher);

        // The pull side is the PubSubSource adapter (the true round-trip),
        // wired with its own stub. PubSubSource owns and closes this stub via
        // close(), so the raw stub is NOT separately closed in tearDown().
        SubscriberStub stub = GrpcSubscriberStub.create(
                SubscriberStubSettings.newBuilder()
                        .setTransportChannelProvider(channelProvider)
                        .setCredentialsProvider(credentialsProvider)
                        .build());
        source = new PubSubSource(stub, SUBSCRIPTION_NAME.toString());
    }

    @AfterAll
    void tearDown() throws InterruptedException {
        if (sink != null) {
            sink.shutdown(10L, TimeUnit.SECONDS);
        }
        // PubSubSource#close() closes the wrapped SubscriberStub.
        if (source != null) {
            source.close();
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

    /**
     * Drive the {@link PubSubSource} adapter's single-pull {@code read}
     * repeatedly until {@code want} payloads have been collected or the bounded
     * attempts run out. The source acks what each pull returns, so re-reads
     * only surface not-yet-pulled messages.
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
    void topicNameReflectsWiredPublisher() {
        assertThat(sink.topicName()).isEqualTo(TOPIC_NAME.toString());
    }

    @Test
    void messagesPublishedViaSinkRoundTripThroughSource() throws InterruptedException {
        // Publish through the PubSubSink adapter under test.
        sink.write(List.of(msg("alpha"), msg("beta"), msg("gamma")).iterator(), null);

        // Pull them back through the PubSubSource adapter: full sink -> source
        // round-trip against the live emulator.
        List<String> bodies = readBodies(3);
        assertThat(bodies).containsExactlyInAnyOrder("alpha", "beta", "gamma");
    }
}
