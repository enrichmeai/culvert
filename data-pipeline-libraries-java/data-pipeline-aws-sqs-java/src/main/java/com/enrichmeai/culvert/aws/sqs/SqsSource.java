package com.enrichmeai.culvert.aws.sqs;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Source;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.DeleteMessageBatchRequest;
import software.amazon.awssdk.services.sqs.model.DeleteMessageBatchRequestEntry;
import software.amazon.awssdk.services.sqs.model.Message;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageRequest;
import software.amazon.awssdk.services.sqs.model.ReceiveMessageResponse;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;

/**
 * {@link Source} implementation backed by an AWS SQS queue.
 *
 * <p>Wraps an {@link SqsClient} and performs a single synchronous
 * {@code receiveMessage} call per {@link #read(RuntimeContext)}. Returned
 * messages are deleted eagerly (by receipt handle) before {@code read}
 * returns, mirroring {@code PubSubSource}'s eager-ack design. The delivery
 * model is therefore <em>at-most-once</em>: a consumer that crashes
 * mid-iteration after {@code read} has returned will lose the received
 * batch, because the messages have already been deleted from the queue and
 * cannot be redelivered. Callers needing at-least-once semantics should
 * defer deletion until the batch has been fully processed downstream (not
 * provided by this class) — this is the SQS analog of the trade-off
 * {@code PubSubSource} documents for eager-ack Pub/Sub pulls.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #SqsSource(SqsClient, String)} — primary; uses the default
 *       {@code maxNumberOfMessages} of {@value #DEFAULT_MAX_MESSAGES} and
 *       {@code waitTimeSeconds} of {@value #DEFAULT_WAIT_TIME_SECONDS} per
 *       receive.</li>
 *   <li>{@link #SqsSource(SqsClient, String, int, int)} — explicit per-call
 *       batch size and long-poll wait time.</li>
 * </ul>
 *
 * <p>{@code queueUrl} must be the queue's full URL (e.g.
 * {@code https://sqs.us-east-1.amazonaws.com/123456789012/my-queue}), as
 * returned by {@code SqsClient#getQueueUrl}.
 *
 * <p>SQS caps {@code maxNumberOfMessages} at 10 per {@code receiveMessage}
 * call and {@code waitTimeSeconds} at 20 (long polling); both constructors
 * validate against those limits.
 *
 * <p>{@link SqsClient} implements {@link AutoCloseable}, so this class also
 * implements {@link AutoCloseable}; closing it closes the wrapped client.
 * Mirrors the {@code PubSubSource} / {@code SecretManagerProvider} pilot's
 * "AutoCloseable only when the wrapped client supports it" rule.
 *
 * <p>Sprint-21 deliverable (T21.3, epic #144).
 */
public final class SqsSource implements Source<Message>, AutoCloseable {

    /** Default per-receive batch size when not specified. */
    public static final int DEFAULT_MAX_MESSAGES = 10;

    /** Default long-poll wait time (seconds) when not specified. */
    public static final int DEFAULT_WAIT_TIME_SECONDS = 0;

    /** SQS hard cap on messages per {@code receiveMessage} call. */
    public static final int MAX_MESSAGES_LIMIT = 10;

    /** SQS hard cap on long-poll wait time, in seconds. */
    public static final int MAX_WAIT_TIME_SECONDS = 20;

    private final SqsClient client;
    private final String queueUrl;
    private final int maxNumberOfMessages;
    private final int waitTimeSeconds;

    /**
     * Primary constructor. Uses {@link #DEFAULT_MAX_MESSAGES} and
     * {@link #DEFAULT_WAIT_TIME_SECONDS}.
     *
     * @param client   Pre-built SQS client. Required. Ownership transfers to
     *                 this source — {@link #close()} will close it.
     * @param queueUrl Full queue URL. Required.
     * @throws NullPointerException if either argument is null.
     */
    public SqsSource(SqsClient client, String queueUrl) {
        this(client, queueUrl, DEFAULT_MAX_MESSAGES, DEFAULT_WAIT_TIME_SECONDS);
    }

    /**
     * Constructor with explicit per-call batch size and long-poll wait time.
     *
     * @param client              Pre-built SQS client. Required.
     * @param queueUrl            Full queue URL. Required.
     * @param maxNumberOfMessages Maximum messages per {@code receiveMessage}
     *                            call. Must be between 1 and
     *                            {@value #MAX_MESSAGES_LIMIT} inclusive.
     * @param waitTimeSeconds     Long-poll wait time in seconds. Must be
     *                            between 0 and {@value #MAX_WAIT_TIME_SECONDS}
     *                            inclusive.
     * @throws NullPointerException     if {@code client} or {@code queueUrl}
     *                                  is null.
     * @throws IllegalArgumentException if {@code maxNumberOfMessages} or
     *                                  {@code waitTimeSeconds} is out of
     *                                  range.
     */
    public SqsSource(SqsClient client, String queueUrl, int maxNumberOfMessages, int waitTimeSeconds) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.queueUrl = Objects.requireNonNull(queueUrl, "queueUrl must not be null");
        if (maxNumberOfMessages < 1 || maxNumberOfMessages > MAX_MESSAGES_LIMIT) {
            throw new IllegalArgumentException(
                    "maxNumberOfMessages must be between 1 and " + MAX_MESSAGES_LIMIT
                            + ", got " + maxNumberOfMessages);
        }
        if (waitTimeSeconds < 0 || waitTimeSeconds > MAX_WAIT_TIME_SECONDS) {
            throw new IllegalArgumentException(
                    "waitTimeSeconds must be between 0 and " + MAX_WAIT_TIME_SECONDS
                            + ", got " + waitTimeSeconds);
        }
        this.maxNumberOfMessages = maxNumberOfMessages;
        this.waitTimeSeconds = waitTimeSeconds;
    }

    /**
     * Issue one synchronous {@code receiveMessage} call against the wired
     * queue and eagerly delete the returned messages.
     *
     * <p>Returns an iterator over the message payloads. If the receive
     * returns no messages the iterator is empty and no delete call is made.
     *
     * @param context Runtime context. Not used by this implementation but
     *                accepted to honour the {@link Source} contract.
     * @return Iterator over the received {@link Message}s.
     */
    @Override
    public Iterator<Message> read(RuntimeContext context) {
        ReceiveMessageRequest request = ReceiveMessageRequest.builder()
                .queueUrl(queueUrl)
                .maxNumberOfMessages(maxNumberOfMessages)
                .waitTimeSeconds(waitTimeSeconds)
                .build();

        ReceiveMessageResponse response = client.receiveMessage(request);
        List<Message> received = response.messages();
        if (received.isEmpty()) {
            return Collections.emptyIterator();
        }

        // Eager delete: remove every received message from the queue before
        // exposing it to the caller. This gives at-most-once semantics —
        // documented on the class — and keeps the iterator simple (no
        // per-message delete callback for the consumer to forget). Mirrors
        // PubSubSource's eager-ack collect-then-acknowledge shape, using
        // deleteMessageBatch (SQS's batch analog of Pub/Sub's acknowledge).
        List<DeleteMessageBatchRequestEntry> deleteEntries = new ArrayList<>(received.size());
        List<Message> payloads = new ArrayList<>(received.size());
        for (Message message : received) {
            deleteEntries.add(DeleteMessageBatchRequestEntry.builder()
                    .id(message.messageId())
                    .receiptHandle(message.receiptHandle())
                    .build());
            payloads.add(message);
        }

        DeleteMessageBatchRequest deleteRequest = DeleteMessageBatchRequest.builder()
                .queueUrl(queueUrl)
                .entries(deleteEntries)
                .build();
        client.deleteMessageBatch(deleteRequest);

        return payloads.iterator();
    }

    /** The full queue URL this source receives from. */
    public String queueUrl() {
        return queueUrl;
    }

    /** The configured maximum messages per receive call. */
    public int maxNumberOfMessages() {
        return maxNumberOfMessages;
    }

    /** The configured long-poll wait time, in seconds. */
    public int waitTimeSeconds() {
        return waitTimeSeconds;
    }

    @Override
    public void close() {
        client.close();
    }
}
