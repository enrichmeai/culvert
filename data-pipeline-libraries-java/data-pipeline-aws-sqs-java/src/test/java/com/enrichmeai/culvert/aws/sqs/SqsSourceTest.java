package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.DeleteMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.Message;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageRequest;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageResponse;

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
 * Unit tests for {@link SqsSource}. Mocks {@link SqsClient} so no real AWS
 * credentials or network are required. Mirrors {@code PubSubSourceTest}'s
 * coverage shape (happy path incl. ack/delete verification, empty receive,
 * request-shape assertions, error propagation, construction validation,
 * close lifecycle).
 */
@ExtendWith(MockitoExtension.class)
class SqsSourceTest {

    private static final String QUEUE_URL =
            "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue";

    @Mock
    private SqsClient client;

    @Mock
    private RuntimeContext context;

    private static Message message(String id, String receiptHandle, String body) {
        return Message.builder()
                .messageId(id)
                .receiptHandle(receiptHandle)
                .body(body)
                .build();
    }

    private static ReceiveMessageResponse receiveResponseWith(Message... msgs) {
        return ReceiveMessageResponse.builder()
                .messages(List.of(msgs))
                .build();
    }

    // --- happy paths -------------------------------------------------------

    @Test
    void readReturnsReceivedMessagesAndDeletesThem() {
        when(client.receiveMessage(any(ReceiveMessageRequest.class))).thenReturn(
                receiveResponseWith(
                        message("id-1", "rh-1", "hello"),
                        message("id-2", "rh-2", "world")));

        SqsSource source = new SqsSource(client, QUEUE_URL);
        Iterator<Message> it = source.read(context);

        List<Message> drained = new ArrayList<>();
        it.forEachRemaining(drained::add);

        assertThat(drained).hasSize(2);
        assertThat(drained.get(0).body()).isEqualTo("hello");
        assertThat(drained.get(1).body()).isEqualTo("world");

        // Both messages carried on a single deleteMessageBatch call.
        ArgumentCaptor<DeleteMessageBatchRequest> deleteCaptor =
                ArgumentCaptor.forClass(DeleteMessageBatchRequest.class);
        verify(client).deleteMessageBatch(deleteCaptor.capture());
        assertThat(deleteCaptor.getValue().entries()).hasSize(2);
        assertThat(deleteCaptor.getValue().entries())
                .extracting(e -> e.receiptHandle())
                .containsExactly("rh-1", "rh-2");
        assertThat(deleteCaptor.getValue().queueUrl()).isEqualTo(QUEUE_URL);
    }

    @Test
    void emptyReceiveYieldsEmptyIteratorAndNoDelete() {
        when(client.receiveMessage(any(ReceiveMessageRequest.class))).thenReturn(
                ReceiveMessageResponse.builder().build());

        SqsSource source = new SqsSource(client, QUEUE_URL);
        Iterator<Message> it = source.read(context);

        assertThat(it.hasNext()).isFalse();
        // Empty receive must NOT issue a delete call (nothing to delete).
        verify(client, never()).deleteMessageBatch(any(DeleteMessageBatchRequest.class));
    }

    @Test
    void receiveRequestCarriesQueueUrlAndMaxMessagesAndWaitTime() {
        when(client.receiveMessage(any(ReceiveMessageRequest.class))).thenReturn(
                receiveResponseWith(message("id", "rh", "x")));

        SqsSource source = new SqsSource(client, QUEUE_URL, 5, 10);
        source.read(context);

        ArgumentCaptor<ReceiveMessageRequest> receiveCaptor =
                ArgumentCaptor.forClass(ReceiveMessageRequest.class);
        verify(client).receiveMessage(receiveCaptor.capture());
        assertThat(receiveCaptor.getValue().queueUrl()).isEqualTo(QUEUE_URL);
        assertThat(receiveCaptor.getValue().maxNumberOfMessages()).isEqualTo(5);
        assertThat(receiveCaptor.getValue().waitTimeSeconds()).isEqualTo(10);
    }

    @Test
    void defaultsAreUsedWhenNotSpecified() {
        SqsSource source = new SqsSource(client, QUEUE_URL);
        assertThat(source.maxNumberOfMessages()).isEqualTo(SqsSource.DEFAULT_MAX_MESSAGES);
        assertThat(source.waitTimeSeconds()).isEqualTo(SqsSource.DEFAULT_WAIT_TIME_SECONDS);
        assertThat(source.queueUrl()).isEqualTo(QUEUE_URL);
    }

    // --- error paths -------------------------------------------------------

    @Test
    void receiveExceptionPropagatesToCaller() {
        when(client.receiveMessage(any(ReceiveMessageRequest.class)))
                .thenThrow(new RuntimeException("sqs unavailable"));

        SqsSource source = new SqsSource(client, QUEUE_URL);

        assertThatThrownBy(() -> source.read(context))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("sqs unavailable");

        // No delete attempted when the receive itself failed.
        verify(client, never()).deleteMessageBatch(any(DeleteMessageBatchRequest.class));
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new SqsSource(null, QUEUE_URL))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullQueueUrl() {
        assertThatThrownBy(() -> new SqsSource(client, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsOutOfRangeMaxMessages() {
        assertThatThrownBy(() -> new SqsSource(client, QUEUE_URL, 0, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SqsSource(client, QUEUE_URL, 11, 0))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructorRejectsOutOfRangeWaitTime() {
        assertThatThrownBy(() -> new SqsSource(client, QUEUE_URL, 10, -1))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SqsSource(client, QUEUE_URL, 10, 21))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void closeDelegatesToClient() {
        SqsSource source = new SqsSource(client, QUEUE_URL);
        source.close();
        verify(client).close();
    }
}
