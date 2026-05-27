package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Source;
import com.google.pubsub.v1.AcknowledgeRequest;
import com.google.pubsub.v1.PubsubMessage;
import com.google.pubsub.v1.PullRequest;
import com.google.pubsub.v1.PullResponse;
import com.google.pubsub.v1.ReceivedMessage;
import com.google.cloud.pubsub.v1.stub.SubscriberStub;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;

/**
 * {@link Source} implementation backed by a Google Cloud Pub/Sub subscription.
 *
 * <p>Wraps a {@link SubscriberStub} and performs a single synchronous
 * {@code pull} per {@link #read(RuntimeContext)} call. Returned messages are
 * acknowledged eagerly before {@code read} returns, so the delivery model is
 * <em>at-most-once</em>: a consumer that crashes mid-iteration after
 * {@code read} has returned will lose the pulled batch. Callers needing
 * at-least-once semantics should wire a separate Subscriber-based reader.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #PubSubSource(SubscriberStub, String)} — primary; uses the
 *       default {@code maxMessages} of {@value #DEFAULT_MAX_MESSAGES} per
 *       pull.</li>
 *   <li>{@link #PubSubSource(SubscriberStub, String, int)} — explicit
 *       per-pull batch size.</li>
 * </ul>
 *
 * <p>{@code subscriptionName} must be the fully-qualified resource name
 * ({@code projects/{project}/subscriptions/{name}}). The
 * {@link com.google.pubsub.v1.ProjectSubscriptionName#of(String, String)
 * ProjectSubscriptionName.of} helper produces the canonical form.
 *
 * <p>The wrapped {@link SubscriberStub} extends
 * {@link com.google.api.gax.core.BackgroundResource} which itself extends
 * {@link AutoCloseable}, so this class also implements {@link AutoCloseable};
 * closing it closes the stub. Mirrors the {@code SecretManagerProvider}
 * pilot's "AutoCloseable only when the wrapped client supports it" rule.
 *
 * <p>Sprint-2 deliverable for issue #23.
 */
public final class PubSubSource implements Source<PubsubMessage>, AutoCloseable {

    /** Default per-pull batch size when not specified. */
    public static final int DEFAULT_MAX_MESSAGES = 100;

    private final SubscriberStub stub;
    private final String subscriptionName;
    private final int maxMessages;

    /**
     * Primary constructor. Uses {@link #DEFAULT_MAX_MESSAGES} per pull.
     *
     * @param stub             Pre-built Pub/Sub subscriber stub. Required.
     *                         Ownership transfers to this source —
     *                         {@link #close()} will close it.
     * @param subscriptionName Fully-qualified subscription resource name
     *                         ({@code projects/{project}/subscriptions/{name}}).
     *                         Required.
     * @throws NullPointerException if either argument is null.
     */
    public PubSubSource(SubscriberStub stub, String subscriptionName) {
        this(stub, subscriptionName, DEFAULT_MAX_MESSAGES);
    }

    /**
     * Constructor with explicit per-pull batch size.
     *
     * @param stub             Pre-built Pub/Sub subscriber stub. Required.
     * @param subscriptionName Fully-qualified subscription resource name.
     *                         Required.
     * @param maxMessages      Maximum messages per {@code pull} call. Must
     *                         be positive.
     * @throws NullPointerException     if {@code stub} or
     *                                  {@code subscriptionName} is null.
     * @throws IllegalArgumentException if {@code maxMessages} is not
     *                                  positive.
     */
    public PubSubSource(SubscriberStub stub, String subscriptionName, int maxMessages) {
        this.stub = Objects.requireNonNull(stub, "stub must not be null");
        this.subscriptionName = Objects.requireNonNull(
                subscriptionName, "subscriptionName must not be null");
        if (maxMessages <= 0) {
            throw new IllegalArgumentException(
                    "maxMessages must be positive, got " + maxMessages);
        }
        this.maxMessages = maxMessages;
    }

    /**
     * Issue one synchronous pull against the wired subscription and
     * eagerly acknowledge the returned messages.
     *
     * <p>Returns an iterator over the message payloads. If the pull returns
     * no messages the iterator is empty and no acknowledge call is made.
     *
     * @param context Runtime context. Not used by this implementation but
     *                accepted to honour the {@link Source} contract.
     * @return Iterator over the pulled {@link PubsubMessage}s.
     */
    @Override
    public Iterator<PubsubMessage> read(RuntimeContext context) {
        PullRequest pullRequest = PullRequest.newBuilder()
                .setSubscription(subscriptionName)
                .setMaxMessages(maxMessages)
                .build();

        PullResponse response = stub.pullCallable().call(pullRequest);
        List<ReceivedMessage> received = response.getReceivedMessagesList();
        if (received.isEmpty()) {
            return Collections.emptyIterator();
        }

        // Eager ack: collect ackIds and acknowledge before exposing
        // messages. This gives at-most-once semantics — documented on the
        // class — and keeps the iterator simple (no per-message ack callback
        // for the consumer to forget).
        List<String> ackIds = new ArrayList<>(received.size());
        List<PubsubMessage> payloads = new ArrayList<>(received.size());
        for (ReceivedMessage rm : received) {
            ackIds.add(rm.getAckId());
            payloads.add(rm.getMessage());
        }

        AcknowledgeRequest ackRequest = AcknowledgeRequest.newBuilder()
                .setSubscription(subscriptionName)
                .addAllAckIds(ackIds)
                .build();
        stub.acknowledgeCallable().call(ackRequest);

        return payloads.iterator();
    }

    /** The fully-qualified subscription name this source pulls from. */
    public String subscriptionName() {
        return subscriptionName;
    }

    /** The configured maximum messages per pull. */
    public int maxMessages() {
        return maxMessages;
    }

    @Override
    public void close() {
        stub.close();
    }
}
