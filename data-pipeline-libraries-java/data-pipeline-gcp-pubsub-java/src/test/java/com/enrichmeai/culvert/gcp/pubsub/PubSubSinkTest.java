package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.google.api.core.ApiFuture;
import com.google.api.core.ApiFutures;
import com.google.cloud.pubsub.v1.Publisher;
import com.google.protobuf.ByteString;
import com.google.pubsub.v1.PubsubMessage;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.IOException;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link PubSubSink}. Mocks {@link Publisher} so no real
 * Pub/Sub credentials or network are required. Uses
 * {@link ApiFutures#immediateFuture(Object)} / {@code immediateFailedFuture}
 * to drive the future-resolution code path deterministically.
 */
@ExtendWith(MockitoExtension.class)
class PubSubSinkTest {

    @Mock
    private Publisher publisher;

    @Mock
    private RuntimeContext context;

    private static PubsubMessage msg(String body) {
        return PubsubMessage.newBuilder()
                .setData(ByteString.copyFromUtf8(body))
                .build();
    }

    private static ApiFuture<String> ok(String messageId) {
        return ApiFutures.immediateFuture(messageId);
    }

    private static ApiFuture<String> fail(Throwable cause) {
        return ApiFutures.immediateFailedFuture(cause);
    }

    // --- happy paths -------------------------------------------------------

    @Test
    void publishSingleMessageResolvesAndReturns() {
        when(publisher.publish(any(PubsubMessage.class))).thenReturn(ok("server-id-1"));

        PubSubSink sink = new PubSubSink(publisher);
        sink.write(List.of(msg("hello")).iterator(), context);

        ArgumentCaptor<PubsubMessage> captor = ArgumentCaptor.forClass(PubsubMessage.class);
        verify(publisher).publish(captor.capture());
        assertThat(captor.getValue().getData().toStringUtf8()).isEqualTo("hello");
    }

    @Test
    void publishMultipleMessagesIssuesOnePublishCallPerRecord() {
        // Chain individual thenReturn calls instead of varargs to avoid the
        // "unchecked generic array creation for varargs parameter" warning
        // that -Werror promotes to an error in this codebase.
        when(publisher.publish(any(PubsubMessage.class)))
                .thenReturn(ok("id-1"))
                .thenReturn(ok("id-2"))
                .thenReturn(ok("id-3"));

        PubSubSink sink = new PubSubSink(publisher);
        Iterator<PubsubMessage> records = List.of(
                msg("a"), msg("b"), msg("c")).iterator();
        sink.write(records, context);

        verify(publisher, times(3)).publish(any(PubsubMessage.class));
    }

    @Test
    void emptyIteratorDoesNotInvokePublisher() {
        PubSubSink sink = new PubSubSink(publisher);
        sink.write(Collections.emptyIterator(), context);

        verify(publisher, never()).publish(any(PubsubMessage.class));
    }

    @Test
    void topicNameDelegatesToPublisher() {
        when(publisher.getTopicNameString()).thenReturn("projects/p/topics/t");
        PubSubSink sink = new PubSubSink(publisher);
        assertThat(sink.topicName()).isEqualTo("projects/p/topics/t");
    }

    // --- error paths -------------------------------------------------------

    @Test
    void publishFailureSurfacesAsPubSubPublishException() {
        when(publisher.publish(any(PubsubMessage.class))).thenReturn(
                fail(new IOException("topic not found")));

        PubSubSink sink = new PubSubSink(publisher);
        Iterator<PubsubMessage> records = List.of(msg("doomed")).iterator();

        assertThatThrownBy(() -> sink.write(records, context))
                .isInstanceOf(PubSubSink.PubSubPublishException.class)
                .hasMessageContaining("topic not found")
                .hasCauseInstanceOf(IOException.class);
    }

    @Test
    void nullRecordsRejected() {
        PubSubSink sink = new PubSubSink(publisher);
        assertThatThrownBy(() -> sink.write(null, context))
                .isInstanceOf(NullPointerException.class);
        verify(publisher, never()).publish(any(PubsubMessage.class));
    }

    @Test
    void constructorRejectsNullPublisher() {
        assertThatThrownBy(() -> new PubSubSink(null))
                .isInstanceOf(NullPointerException.class);
    }

    // --- lifecycle ---------------------------------------------------------

    @Test
    void shutdownDelegatesToPublisher() throws InterruptedException {
        when(publisher.awaitTermination(5L, TimeUnit.SECONDS)).thenReturn(true);

        PubSubSink sink = new PubSubSink(publisher);
        boolean terminated = sink.shutdown(5L, TimeUnit.SECONDS);

        assertThat(terminated).isTrue();
        verify(publisher).shutdown();
        verify(publisher).awaitTermination(5L, TimeUnit.SECONDS);
    }
}
