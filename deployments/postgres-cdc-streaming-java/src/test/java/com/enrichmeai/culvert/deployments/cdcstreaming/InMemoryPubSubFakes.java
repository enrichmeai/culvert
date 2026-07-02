package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracts.Source;
import com.google.protobuf.ByteString;
import com.google.pubsub.v1.PubsubMessage;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * In-memory {@link Source}/{@link Sink} test doubles over
 * {@link PubsubMessage}, standing in for
 * {@link com.enrichmeai.culvert.gcp.pubsub.PubSubSource}/
 * {@link com.enrichmeai.culvert.gcp.pubsub.PubSubSink} in unit tests — no
 * live Pub/Sub subscription/topic is needed. Mirrors the
 * "Recording*"/"InMemory*" naming convention used by reference-e2e-gcp's
 * test doubles (e.g. {@code RecordingObservabilityHook}).
 */
final class InMemoryPubSubFakes {

    private InMemoryPubSubFakes() {
    }

    static PubsubMessage messageOf(String payload) {
        return PubsubMessage.newBuilder()
                .setData(ByteString.copyFrom(payload, StandardCharsets.UTF_8))
                .build();
    }

    /** Queues a fixed batch of messages to hand back on the first {@link #read}, then empties. */
    static final class QueueSource implements Source<PubsubMessage>, java.io.Serializable {
        private final List<PubsubMessage> queued;
        private boolean drained = false;

        QueueSource(List<String> payloads) {
            this.queued = new ArrayList<>();
            for (String payload : payloads) {
                queued.add(messageOf(payload));
            }
        }

        @Override
        public Iterator<PubsubMessage> read(RuntimeContext context) {
            if (drained) {
                return List.<PubsubMessage>of().iterator();
            }
            drained = true;
            return queued.iterator();
        }
    }

    /** Records every message written via {@link #write}. */
    static final class RecordingSink implements Sink<PubsubMessage>, java.io.Serializable {
        final List<PubsubMessage> written = new ArrayList<>();

        @Override
        public void write(Iterator<PubsubMessage> records, RuntimeContext context) {
            records.forEachRemaining(written::add);
        }

        List<String> writtenPayloads() {
            List<String> payloads = new ArrayList<>();
            for (PubsubMessage message : written) {
                payloads.add(message.getData().toStringUtf8());
            }
            return payloads;
        }
    }
}
