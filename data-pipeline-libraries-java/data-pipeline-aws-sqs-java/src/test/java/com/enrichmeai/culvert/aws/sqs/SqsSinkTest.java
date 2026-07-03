package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.BatchResultErrorEntry;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchResponse;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchResultEntry;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SqsSink}. Mocks {@link SqsClient} so no real AWS
 * credentials or network are required. Mirrors {@code PubSubSinkTest}'s
 * coverage shape (happy path, batching behaviour, empty input, partial
 * failure surfacing, null-rejection, construction validation, close
 * lifecycle) adapted to SQS's per-batch (rather than per-message future)
 * send model.
 */
@ExtendWith(MockitoExtension.class)
class SqsSinkTest {

    private static final String QUEUE_URL =
            "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue";

    @Mock
    private SqsClient client;

    @Mock
    private RuntimeContext context;

    private static SendMessageBatchResponse allSucceeded(int count) {
        List<SendMessageBatchResultEntry> successful = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            successful.add(SendMessageBatchResultEntry.builder()
                    .id(Integer.toString(i))
                    .messageId("msg-" + i)
                    .build());
        }
        return SendMessageBatchResponse.builder().successful(successful).build();
    }

    // --- happy paths -------------------------------------------------------

    @Test
    void writeSingleMessageSendsOneBatchCall() {
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class)))
                .thenReturn(allSucceeded(1));

        SqsSink sink = new SqsSink(client, QUEUE_URL);
        sink.write(List.of("hello").iterator(), context);

        ArgumentCaptor<SendMessageBatchRequest> captor =
                ArgumentCaptor.forClass(SendMessageBatchRequest.class);
        verify(client).sendMessageBatch(captor.capture());
        assertThat(captor.getValue().queueUrl()).isEqualTo(QUEUE_URL);
        assertThat(captor.getValue().entries()).hasSize(1);
        assertThat(captor.getValue().entries().get(0).messageBody()).isEqualTo("hello");
    }

    @Test
    void writePartitionsMoreThanMaxBatchSizeIntoMultipleCalls() {
        // 25 records -> batches of 10, 10, 5.
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class)))
                .thenReturn(allSucceeded(10))
                .thenReturn(allSucceeded(10))
                .thenReturn(allSucceeded(5));

        List<String> records = new ArrayList<>();
        for (int i = 0; i < 25; i++) {
            records.add("msg-" + i);
        }

        SqsSink sink = new SqsSink(client, QUEUE_URL);
        sink.write(records.iterator(), context);

        ArgumentCaptor<SendMessageBatchRequest> captor =
                ArgumentCaptor.forClass(SendMessageBatchRequest.class);
        verify(client, times(3)).sendMessageBatch(captor.capture());
        List<SendMessageBatchRequest> calls = captor.getAllValues();
        assertThat(calls.get(0).entries()).hasSize(10);
        assertThat(calls.get(1).entries()).hasSize(10);
        assertThat(calls.get(2).entries()).hasSize(5);
    }

    @Test
    void writeExactMultipleOfMaxBatchSizeIssuesExactBatchCount() {
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class)))
                .thenReturn(allSucceeded(10))
                .thenReturn(allSucceeded(10));

        List<String> records = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            records.add("msg-" + i);
        }

        SqsSink sink = new SqsSink(client, QUEUE_URL);
        sink.write(records.iterator(), context);

        verify(client, times(2)).sendMessageBatch(any(SendMessageBatchRequest.class));
    }

    @Test
    void emptyIteratorDoesNotInvokeClient() {
        SqsSink sink = new SqsSink(client, QUEUE_URL);
        sink.write(Collections.emptyIterator(), context);

        verify(client, never()).sendMessageBatch(any(SendMessageBatchRequest.class));
    }

    @Test
    void queueUrlAccessorReturnsWiredUrl() {
        SqsSink sink = new SqsSink(client, QUEUE_URL);
        assertThat(sink.queueUrl()).isEqualTo(QUEUE_URL);
    }

    // --- error paths -------------------------------------------------------

    @Test
    void partialBatchFailureSurfacesAsSqsPublishException() {
        SendMessageBatchResponse response = SendMessageBatchResponse.builder()
                .successful(SendMessageBatchResultEntry.builder()
                        .id("0").messageId("msg-0").build())
                .failed(BatchResultErrorEntry.builder()
                        .id("1")
                        .code("InternalError")
                        .senderFault(false)
                        .message("queue not found")
                        .build())
                .build();
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class))).thenReturn(response);

        SqsSink sink = new SqsSink(client, QUEUE_URL);
        Iterator<String> records = List.of("ok", "doomed").iterator();

        assertThatThrownBy(() -> sink.write(records, context))
                .isInstanceOf(SqsSink.SqsPublishException.class)
                .hasMessageContaining("id=1")
                .hasMessageContaining("queue not found");
    }

    @Test
    void laterBatchFailureDoesNotUndoEarlierSuccessfulBatch() {
        // First batch (10 msgs) succeeds; second batch (remaining 2) fails.
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class)))
                .thenReturn(allSucceeded(10))
                .thenReturn(SendMessageBatchResponse.builder()
                        .failed(BatchResultErrorEntry.builder()
                                .id("0")
                                .code("InternalError")
                                .senderFault(false)
                                .message("throttled")
                                .build())
                        .build());

        List<String> records = new ArrayList<>();
        for (int i = 0; i < 12; i++) {
            records.add("msg-" + i);
        }

        SqsSink sink = new SqsSink(client, QUEUE_URL);
        assertThatThrownBy(() -> sink.write(records.iterator(), context))
                .isInstanceOf(SqsSink.SqsPublishException.class);

        // Both calls were made — the first batch's success is not rolled back.
        verify(client, times(2)).sendMessageBatch(any(SendMessageBatchRequest.class));
    }

    @Test
    void nullRecordsRejected() {
        SqsSink sink = new SqsSink(client, QUEUE_URL);
        assertThatThrownBy(() -> sink.write(null, context))
                .isInstanceOf(NullPointerException.class);
        verify(client, never()).sendMessageBatch(any(SendMessageBatchRequest.class));
    }

    @Test
    void nullMessageInIteratorRejected() {
        SqsSink sink = new SqsSink(client, QUEUE_URL);
        List<String> withNull = new ArrayList<>();
        withNull.add("ok");
        withNull.add(null);

        assertThatThrownBy(() -> sink.write(withNull.iterator(), context))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new SqsSink(null, QUEUE_URL))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullQueueUrl() {
        assertThatThrownBy(() -> new SqsSink(client, null))
                .isInstanceOf(NullPointerException.class);
    }

    // --- lifecycle ---------------------------------------------------------

    @Test
    void closeDelegatesToClient() {
        SqsSink sink = new SqsSink(client, QUEUE_URL);
        sink.close();
        verify(client).close();
    }
}
