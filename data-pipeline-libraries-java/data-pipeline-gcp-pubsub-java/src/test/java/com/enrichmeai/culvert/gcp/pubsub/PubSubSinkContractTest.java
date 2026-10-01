package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracttests.SinkContractTest;
import com.google.api.core.ApiFutures;
import com.google.cloud.pubsub.v1.Publisher;
import com.google.protobuf.ByteString;
import com.google.pubsub.v1.PubsubMessage;

import java.util.ArrayList;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link PubSubSink} against the shared {@link SinkContractTest}.
 *
 * <p>The backend double is a mocked {@link Publisher} (the same seam as
 * {@code PubSubSinkTest}) that records each published message in call order,
 * or returns a failed future once told to reject. {@code PubSubSink} is not
 * {@link AutoCloseable} ({@code Publisher} is not), so the suite skips its
 * two close cases. The round trip against the emulator stays in
 * {@code PubSubSinkIT} under {@code -P it}.
 */
class PubSubSinkContractTest extends SinkContractTest<PubsubMessage> {

    private final List<PubsubMessage> published = new ArrayList<>();
    private boolean rejecting;

    @Override
    protected Sink<PubsubMessage> sink() {
        Publisher publisher = mock(Publisher.class);
        when(publisher.publish(any(PubsubMessage.class))).thenAnswer(invocation -> {
            if (rejecting) {
                return ApiFutures.immediateFailedFuture(
                        new IllegalStateException("publish rejected"));
            }
            PubsubMessage message = invocation.getArgument(0);
            published.add(message);
            return ApiFutures.immediateFuture("message-" + published.size());
        });
        return new PubSubSink(publisher);
    }

    @Override
    protected List<PubsubMessage> sentToBackend() {
        return published;
    }

    @Override
    protected PubsubMessage record(int i) {
        return PubsubMessage.newBuilder().setData(ByteString.copyFromUtf8("record-" + i)).build();
    }

    @Override
    protected void backendRejectsWrites() {
        rejecting = true;
    }
}
