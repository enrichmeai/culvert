package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.contracttests.SourceContractTest;
import com.google.api.gax.rpc.UnaryCallable;
import com.google.cloud.pubsub.v1.stub.SubscriberStub;
import com.google.protobuf.ByteString;
import com.google.protobuf.Empty;
import com.google.pubsub.v1.AcknowledgeRequest;
import com.google.pubsub.v1.PubsubMessage;
import com.google.pubsub.v1.PullRequest;
import com.google.pubsub.v1.PullResponse;
import com.google.pubsub.v1.ReceivedMessage;

import java.util.ArrayList;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link PubSubSource} against the shared {@link SourceContractTest}.
 *
 * <p>The backend double is a mocked {@link SubscriberStub} (the same seam as
 * {@code PubSubSourceTest}) whose pull returns the backlog and which refuses
 * pulls once closed. Plain {@code mock()} (lenient) because not every case
 * reaches every stub. The round trip against the emulator stays in
 * {@code PubSubSourceIT} under {@code -P it}.
 */
class PubSubSourceContractTest extends SourceContractTest<PubsubMessage> {

    private static final String SUBSCRIPTION = "projects/contract-project/subscriptions/contract-sub";

    private final List<PubsubMessage> backlog = new ArrayList<>();
    private boolean closed;

    @Override
    protected Source<PubsubMessage> source() {
        SubscriberStub stub = mock(SubscriberStub.class);
        @SuppressWarnings("unchecked")
        UnaryCallable<PullRequest, PullResponse> pull = mock(UnaryCallable.class);
        @SuppressWarnings("unchecked")
        UnaryCallable<AcknowledgeRequest, Empty> ack = mock(UnaryCallable.class);
        when(stub.pullCallable()).thenReturn(pull);
        when(stub.acknowledgeCallable()).thenReturn(ack);
        when(pull.call(any(PullRequest.class))).thenAnswer(invocation -> {
            if (closed) {
                throw new IllegalStateException("subscriber stub is closed");
            }
            PullResponse.Builder response = PullResponse.newBuilder();
            for (int i = 0; i < backlog.size(); i++) {
                response.addReceivedMessages(ReceivedMessage.newBuilder()
                        .setAckId("ack-" + i)
                        .setMessage(backlog.get(i)));
            }
            return response.build();
        });
        doAnswer(invocation -> {
            closed = true;
            return null;
        }).when(stub).close();
        return new PubSubSource(stub, SUBSCRIPTION);
    }

    @Override
    protected void backlog(List<PubsubMessage> records) {
        backlog.addAll(records);
    }

    @Override
    protected PubsubMessage record(int i) {
        return PubsubMessage.newBuilder().setData(ByteString.copyFromUtf8("record-" + i)).build();
    }

    @Override
    protected boolean backendClosed() {
        return closed;
    }
}
