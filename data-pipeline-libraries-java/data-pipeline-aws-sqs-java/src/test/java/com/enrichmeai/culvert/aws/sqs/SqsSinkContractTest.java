package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracttests.SinkContractTest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.BatchResultErrorEntry;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchRequestEntry;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchResponse;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchResultEntry;

import java.util.ArrayList;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link SqsSink} against the shared {@link SinkContractTest}.
 *
 * <p>The backend double is a mocked {@link SqsClient} (the same seam as
 * {@code SqsSinkTest}) that records every batch entry's body in request
 * order. Once told to reject, it reports every entry as failed, the way
 * {@code sendMessageBatch} reports a partial failure rather than throwing.
 * It refuses calls once closed. The round trip against LocalStack stays in
 * {@code SqsLocalStackIT} under {@code -P it}.
 */
class SqsSinkContractTest extends SinkContractTest<String> {

    private static final String QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/contract-queue";

    private final List<String> sent = new ArrayList<>();
    private boolean rejecting;
    private boolean closed;

    @Override
    protected Sink<String> sink() {
        SqsClient client = mock(SqsClient.class);
        when(client.sendMessageBatch(any(SendMessageBatchRequest.class))).thenAnswer(invocation -> {
            if (closed) {
                throw new IllegalStateException("SQS client is closed");
            }
            SendMessageBatchRequest request = invocation.getArgument(0);
            SendMessageBatchResponse.Builder response = SendMessageBatchResponse.builder();
            List<SendMessageBatchResultEntry> successful = new ArrayList<>();
            List<BatchResultErrorEntry> failed = new ArrayList<>();
            for (SendMessageBatchRequestEntry entry : request.entries()) {
                if (rejecting) {
                    failed.add(BatchResultErrorEntry.builder()
                            .id(entry.id()).code("InternalError").senderFault(false).build());
                } else {
                    sent.add(entry.messageBody());
                    successful.add(SendMessageBatchResultEntry.builder()
                            .id(entry.id()).messageId("message-" + sent.size()).build());
                }
            }
            return response.successful(successful).failed(failed).build();
        });
        doAnswer(invocation -> {
            closed = true;
            return null;
        }).when(client).close();
        return new SqsSink(client, QUEUE_URL);
    }

    @Override
    protected List<String> sentToBackend() {
        return sent;
    }

    @Override
    protected String record(int i) {
        return "record-" + i;
    }

    @Override
    protected void backendRejectsWrites() {
        rejecting = true;
    }

    @Override
    protected boolean backendClosed() {
        return closed;
    }
}
