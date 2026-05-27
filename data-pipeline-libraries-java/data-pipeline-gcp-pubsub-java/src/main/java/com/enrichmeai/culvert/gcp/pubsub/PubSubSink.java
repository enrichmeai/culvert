package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import com.google.api.core.ApiFuture;
import com.google.api.core.ApiFutures;
import com.google.cloud.pubsub.v1.Publisher;
import com.google.pubsub.v1.PubsubMessage;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/**
 * {@link Sink} implementation backed by a Google Cloud Pub/Sub topic.
 *
 * <p>Wraps a {@link Publisher} and forwards each record via
 * {@link Publisher#publish(PubsubMessage)}. {@code publish} is asynchronous
 * (returns an {@link ApiFuture}); this sink collects all futures emitted by
 * a single {@link #write(Iterator, RuntimeContext)} call and waits for them
 * to resolve before returning, so any per-message publish failure surfaces
 * to the caller as a {@link PubSubPublishException} rather than being
 * silently dropped.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #PubSubSink(Publisher)} — primary; the topic name is carried
 *       on the {@link Publisher} itself
 *       ({@link Publisher#getTopicNameString()}).</li>
 * </ul>
 *
 * <h2>Lifecycle</h2>
 *
 * <p>{@link Publisher} does NOT implement {@link AutoCloseable} — it exposes
 * {@link Publisher#shutdown()} + {@link Publisher#awaitTermination(long, TimeUnit)}
 * instead. Per the framework's "AutoCloseable only when the wrapped client
 * supports it" rule, this sink also does not implement {@code AutoCloseable}.
 * Callers should invoke {@link #shutdown(long, TimeUnit)} (or manage the
 * Publisher lifecycle externally) when the pipeline finishes.
 *
 * <p>Sprint-2 deliverable for issue #23.
 */
public final class PubSubSink implements Sink<PubsubMessage> {

    private final Publisher publisher;

    /**
     * Primary constructor.
     *
     * @param publisher Pre-built Pub/Sub publisher (already wired with a
     *                  topic and any batching / retry settings the caller
     *                  wants). Required.
     * @throws NullPointerException if {@code publisher} is null.
     */
    public PubSubSink(Publisher publisher) {
        this.publisher = Objects.requireNonNull(publisher, "publisher must not be null");
    }

    /**
     * Publish every record from {@code records}, blocking until all
     * resulting futures resolve.
     *
     * <p>If any individual publish fails, this method throws a
     * {@link PubSubPublishException} that wraps the underlying cause. The
     * iterator is consumed fully before the wait, so partial failures of a
     * batch still surface — but later records in the same batch may have
     * already been published.
     *
     * @param records Records to publish. Must not be null.
     * @param context Runtime context. Not used by this implementation but
     *                accepted to honour the {@link Sink} contract.
     * @throws NullPointerException   if {@code records} is null.
     * @throws PubSubPublishException if any publish future fails.
     */
    @Override
    public void write(Iterator<PubsubMessage> records, RuntimeContext context) {
        Objects.requireNonNull(records, "records must not be null");

        List<ApiFuture<String>> futures = new ArrayList<>();
        while (records.hasNext()) {
            PubsubMessage message = records.next();
            if (message == null) {
                throw new NullPointerException(
                        "records iterator yielded a null PubsubMessage");
            }
            futures.add(publisher.publish(message));
        }

        if (futures.isEmpty()) {
            return;
        }

        try {
            // allAsList resolves when every future resolves; if any fails the
            // composite future fails with the first cause, which surfaces here.
            ApiFutures.allAsList(futures).get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new PubSubPublishException(
                    "Interrupted while waiting for Pub/Sub publish futures", e);
        } catch (ExecutionException e) {
            throw new PubSubPublishException(
                    "Pub/Sub publish failed: " + e.getCause().getMessage(),
                    e.getCause());
        }
    }

    /**
     * Trigger an orderly shutdown of the underlying {@link Publisher} and
     * wait up to {@code timeout} for in-flight publishes to complete.
     *
     * <p>This is a passthrough — the framework does not call it
     * automatically. Wire it into your pipeline teardown hook.
     *
     * @param timeout Maximum time to wait.
     * @param unit    Time unit for {@code timeout}.
     * @return {@code true} if the publisher terminated within the timeout.
     * @throws InterruptedException if the calling thread is interrupted
     *                              while waiting.
     */
    public boolean shutdown(long timeout, TimeUnit unit) throws InterruptedException {
        publisher.shutdown();
        return publisher.awaitTermination(timeout, unit);
    }

    /** The topic name the underlying publisher is targeting. */
    public String topicName() {
        return publisher.getTopicNameString();
    }

    /**
     * Exception thrown when a Pub/Sub publish fails. Wraps the underlying
     * cause so callers can inspect the GCP-side error without depending on
     * the SDK's exception hierarchy at the catch site.
     */
    public static final class PubSubPublishException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public PubSubPublishException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
