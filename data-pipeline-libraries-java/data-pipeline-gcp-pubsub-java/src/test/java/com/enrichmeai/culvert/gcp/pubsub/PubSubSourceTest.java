package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.google.api.gax.rpc.UnaryCallable;
import com.google.cloud.pubsub.v1.stub.SubscriberStub;
import com.google.protobuf.ByteString;
import com.google.protobuf.Empty;
import com.google.pubsub.v1.AcknowledgeRequest;
import com.google.pubsub.v1.PubsubMessage;
import com.google.pubsub.v1.PullRequest;
import com.google.pubsub.v1.PullResponse;
import com.google.pubsub.v1.ReceivedMessage;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link PubSubSource}. Mocks {@link SubscriberStub} so no
 * real Pub/Sub credentials or network are required.
 */
@ExtendWith(MockitoExtension.class)
class PubSubSourceTest {

    private static final String SUBSCRIPTION =
            "projects/my-project/subscriptions/my-sub";

    @Mock
    private SubscriberStub stub;

    @Mock
    private UnaryCallable<PullRequest, PullResponse> pullCallable;

    @Mock
    private UnaryCallable<AcknowledgeRequest, Empty> ackCallable;

    @Mock
    private RuntimeContext context;

    private static PubsubMessage msg(String body) {
        return PubsubMessage.newBuilder()
                .setData(ByteString.copyFromUtf8(body))
                .build();
    }

    private static ReceivedMessage received(String ackId, String body) {
        return ReceivedMessage.newBuilder()
                .setAckId(ackId)
                .setMessage(msg(body))
                .build();
    }

    private static PullResponse pullResponseWith(ReceivedMessage... msgs) {
        return PullResponse.newBuilder()
                .addAllReceivedMessages(List.of(msgs))
                .build();
    }

    // --- happy paths -------------------------------------------------------

    @Test
    void readReturnsPulledMessagesAndAcksThem() {
        when(stub.pullCallable()).thenReturn(pullCallable);
        when(stub.acknowledgeCallable()).thenReturn(ackCallable);
        when(pullCallable.call(any(PullRequest.class))).thenReturn(
                pullResponseWith(received("ack-1", "hello"), received("ack-2", "world")));

        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION);
        Iterator<PubsubMessage> it = source.read(context);

        List<PubsubMessage> drained = new ArrayList<>();
        it.forEachRemaining(drained::add);

        assertThat(drained).hasSize(2);
        assertThat(drained.get(0).getData().toStringUtf8()).isEqualTo("hello");
        assertThat(drained.get(1).getData().toStringUtf8()).isEqualTo("world");

        // Both ackIds carried on a single acknowledge call.
        ArgumentCaptor<AcknowledgeRequest> ackCaptor =
                ArgumentCaptor.forClass(AcknowledgeRequest.class);
        verify(ackCallable).call(ackCaptor.capture());
        assertThat(ackCaptor.getValue().getAckIdsList())
                .containsExactly("ack-1", "ack-2");
        assertThat(ackCaptor.getValue().getSubscription()).isEqualTo(SUBSCRIPTION);
    }

    @Test
    void emptyPullYieldsEmptyIteratorAndNoAck() {
        when(stub.pullCallable()).thenReturn(pullCallable);
        when(pullCallable.call(any(PullRequest.class))).thenReturn(
                PullResponse.getDefaultInstance());

        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION);
        Iterator<PubsubMessage> it = source.read(context);

        assertThat(it.hasNext()).isFalse();
        // Empty pull must NOT issue an acknowledge call (no ackIds to send).
        verify(stub, never()).acknowledgeCallable();
    }

    @Test
    void pullRequestCarriesSubscriptionAndMaxMessages() {
        when(stub.pullCallable()).thenReturn(pullCallable);
        when(stub.acknowledgeCallable()).thenReturn(ackCallable);
        when(pullCallable.call(any(PullRequest.class))).thenReturn(
                pullResponseWith(received("a", "x")));

        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION, 25);
        source.read(context);

        ArgumentCaptor<PullRequest> pullCaptor =
                ArgumentCaptor.forClass(PullRequest.class);
        verify(pullCallable).call(pullCaptor.capture());
        assertThat(pullCaptor.getValue().getSubscription()).isEqualTo(SUBSCRIPTION);
        assertThat(pullCaptor.getValue().getMaxMessages()).isEqualTo(25);
    }

    @Test
    void defaultMaxMessagesIsUsedWhenNotSpecified() {
        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION);
        assertThat(source.maxMessages()).isEqualTo(PubSubSource.DEFAULT_MAX_MESSAGES);
        assertThat(source.subscriptionName()).isEqualTo(SUBSCRIPTION);
    }

    // --- error paths -------------------------------------------------------

    @Test
    void pullExceptionPropagatesToCaller() {
        when(stub.pullCallable()).thenReturn(pullCallable);
        when(pullCallable.call(any(PullRequest.class)))
                .thenThrow(new RuntimeException("pubsub unavailable"));

        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION);

        assertThatThrownBy(() -> source.read(context))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("pubsub unavailable");

        // No acknowledge attempted when the pull itself failed.
        verify(stub, never()).acknowledgeCallable();
    }

    @Test
    void constructorRejectsNullStub() {
        assertThatThrownBy(() -> new PubSubSource(null, SUBSCRIPTION))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullSubscription() {
        assertThatThrownBy(() -> new PubSubSource(stub, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNonPositiveMaxMessages() {
        assertThatThrownBy(() -> new PubSubSource(stub, SUBSCRIPTION, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new PubSubSource(stub, SUBSCRIPTION, -1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void closeDelegatesToStub() {
        PubSubSource source = new PubSubSource(stub, SUBSCRIPTION);
        source.close();
        verify(stub).close();
    }
}
