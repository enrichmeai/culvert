package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.contracttests.SourceContractTest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.DeleteMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.DeleteMessageBatchResponse;
import software.amazon.awssdk.services.sqs.model.Message;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageRequest;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageResponse;

import java.util.ArrayList;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link SqsSource} against the shared {@link SourceContractTest}.
 *
 * <p>The backend double is a mocked {@link SqsClient} (the same seam as
 * {@code SqsSourceTest}) whose receive returns the backlog and which refuses
 * calls once closed. The round trip against LocalStack stays in
 * {@code SqsLocalStackIT} under {@code -P it}.
 */
class SqsSourceContractTest extends SourceContractTest<Message> {

    private static final String QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/contract-queue";

    private final List<Message> backlog = new ArrayList<>();
    private boolean closed;

    @Override
    protected Source<Message> source() {
        SqsClient client = mock(SqsClient.class);
        when(client.receiveMessage(any(ReceiveMessageRequest.class))).thenAnswer(invocation -> {
            if (closed) {
                throw new IllegalStateException("SQS client is closed");
            }
            return ReceiveMessageResponse.builder().messages(backlog).build();
        });
        when(client.deleteMessageBatch(any(DeleteMessageBatchRequest.class)))
                .thenReturn(DeleteMessageBatchResponse.builder().build());
        doAnswer(invocation -> {
            closed = true;
            return null;
        }).when(client).close();
        return new SqsSource(client, QUEUE_URL);
    }

    @Override
    protected void backlog(List<Message> records) {
        backlog.addAll(records);
    }

    @Override
    protected Message record(int i) {
        return Message.builder()
                .messageId("id-" + i)
                .receiptHandle("receipt-" + i)
                .body("record-" + i)
                .build();
    }

    @Override
    protected boolean backendClosed() {
        return closed;
    }
}
