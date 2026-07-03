package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.BatchResultErrorEntry;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchRequestEntry;
import software.amazon.awssdk.services.sqs.model.SendMessageBatchResponse;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;

/**
 * {@link Sink} implementation backed by an AWS SQS queue.
 *
 * <p>Wraps an {@link SqsClient} and forwards records via
 * {@code sendMessageBatch}, SQS's batch analog of Pub/Sub's per-message
 * {@code publish}. SQS caps a single {@code sendMessageBatch} call at
 * {@value #MAX_BATCH_SIZE} entries, so {@link #write(Iterator, RuntimeContext)}
 * partitions the incoming records into batches of that size and issues one
 * call per batch. Unlike {@code PubSubSink} (which fires all publishes
 * concurrently and waits on the composite future), this sink's calls are
 * synchronous per batch — {@code sendMessageBatch} itself is a single
 * blocking round-trip covering up to {@value #MAX_BATCH_SIZE} messages.
 *
 * <p>SQS's batch API reports partial failure per-entry rather than failing
 * the whole call: a response can contain both {@code successful} and
 * {@code failed} entries. Any non-empty {@code failed} list surfaces to the
 * caller as a {@link SqsPublishException} summarising the failed entries,
 * mirroring {@code PubSubSink}'s "collect then fail loudly" behaviour rather
 * than silently dropping records. Entries in the same batch that already
 * succeeded remain delivered — the exception reports the failure, it does
 * not roll anything back.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #SqsSink(SqsClient, String)} — primary; queue URL supplied
 *       explicitly since {@link SqsClient} carries no notion of a "current"
 *       queue the way a Pub/Sub {@code Publisher} is bound to one topic.</li>
 * </ul>
 *
 * <h2>Lifecycle</h2>
 *
 * <p>{@link SqsClient} implements {@link AutoCloseable}, so — unlike
 * {@code PubSubSink}, whose wrapped {@code Publisher} does not — this sink
 * also implements {@link AutoCloseable}; {@link #close()} closes the wrapped
 * client. Mirrors the framework's "AutoCloseable only when the wrapped
 * client supports it" rule from the other direction.
 *
 * <p>Sprint-21 deliverable (T21.3, epic #144).
 */
public final class SqsSink implements Sink<String>, AutoCloseable {

    /** SQS hard cap on entries per {@code sendMessageBatch} call. */
    public static final int MAX_BATCH_SIZE = 10;

    private final SqsClient client;
    private final String queueUrl;

    /**
     * Primary constructor.
     *
     * @param client   Pre-built SQS client. Required. Ownership transfers to
     *                 this sink — {@link #close()} will close it.
     * @param queueUrl Full queue URL to send to. Required.
     * @throws NullPointerException if either argument is null.
     */
    public SqsSink(SqsClient client, String queueUrl) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.queueUrl = Objects.requireNonNull(queueUrl, "queueUrl must not be null");
    }

    /**
     * Send every record from {@code records} to the wired queue, batching
     * up to {@value #MAX_BATCH_SIZE} messages per {@code sendMessageBatch}
     * call.
     *
     * <p>If any entry in any batch fails, this method throws a
     * {@link SqsPublishException} summarising the failed entries. The
     * iterator is consumed one batch at a time, so a failure in an earlier
     * batch still allows later batches to have already been sent — mirrors
     * {@code PubSubSink}'s "later records in the same call may have already
     * published" partial-failure trade-off.
     *
     * @param records Records to send. Must not be null.
     * @param context Runtime context. Not used by this implementation but
     *                accepted to honour the {@link Sink} contract.
     * @throws NullPointerException if {@code records} is null.
     * @throws SqsPublishException  if any batch entry fails to send.
     */
    @Override
    public void write(Iterator<String> records, RuntimeContext context) {
        Objects.requireNonNull(records, "records must not be null");

        List<String> batch = new ArrayList<>(MAX_BATCH_SIZE);
        while (records.hasNext()) {
            String message = records.next();
            if (message == null) {
                throw new NullPointerException(
                        "records iterator yielded a null message body");
            }
            batch.add(message);
            if (batch.size() == MAX_BATCH_SIZE) {
                sendBatch(batch);
                batch.clear();
            }
        }
        if (!batch.isEmpty()) {
            sendBatch(batch);
        }
    }

    /** Send one batch (at most {@link #MAX_BATCH_SIZE} entries) and check for partial failure. */
    private void sendBatch(List<String> bodies) {
        List<SendMessageBatchRequestEntry> entries = new ArrayList<>(bodies.size());
        for (int i = 0; i < bodies.size(); i++) {
            entries.add(SendMessageBatchRequestEntry.builder()
                    .id(Integer.toString(i))
                    .messageBody(bodies.get(i))
                    .build());
        }

        SendMessageBatchRequest request = SendMessageBatchRequest.builder()
                .queueUrl(queueUrl)
                .entries(entries)
                .build();

        SendMessageBatchResponse response = client.sendMessageBatch(request);
        if (response.hasFailed() && !response.failed().isEmpty()) {
            throw new SqsPublishException(summarizeFailures(response.failed()));
        }
    }

    private static String summarizeFailures(List<BatchResultErrorEntry> failed) {
        StringBuilder sb = new StringBuilder("SQS sendMessageBatch reported ")
                .append(failed.size())
                .append(" failed entr")
                .append(failed.size() == 1 ? "y" : "ies")
                .append(": ");
        for (int i = 0; i < failed.size(); i++) {
            BatchResultErrorEntry entry = failed.get(i);
            if (i > 0) {
                sb.append("; ");
            }
            sb.append("id=").append(entry.id())
                    .append(" code=").append(entry.code())
                    .append(" senderFault=").append(entry.senderFault())
                    .append(" message=").append(entry.message());
        }
        return sb.toString();
    }

    /** The full queue URL this sink sends to. */
    public String queueUrl() {
        return queueUrl;
    }

    @Override
    public void close() {
        client.close();
    }

    /**
     * Exception thrown when one or more entries of an SQS
     * {@code sendMessageBatch} call fail. Wraps a human-readable summary of
     * the failed entries so callers can inspect the AWS-side error without
     * depending on the SDK's response shape at the catch site.
     */
    public static final class SqsPublishException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public SqsPublishException(String message) {
            super(message);
        }
    }
}
