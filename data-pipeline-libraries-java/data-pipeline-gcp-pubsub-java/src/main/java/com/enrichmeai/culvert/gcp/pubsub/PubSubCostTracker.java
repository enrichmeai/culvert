package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Objects;

/**
 * Builds a {@link CostMetrics} record from Pub/Sub message-count and
 * throughput-bytes, and pushes it to the {@link FinOpsSink}.
 *
 * <h2>Supported operations</h2>
 * <ul>
 *   <li><b>Publish</b>: {@link #trackPublish(long, long, String, FinOpsTag)} —
 *       records {@code billedMessagesCount} and {@code billedBytesWritten};
 *       estimates USD from throughput bytes using {@link #THROUGHPUT_COST_USD_PER_TIB}.</li>
 *   <li><b>Subscribe</b>: {@link #trackSubscribe(long, long, String, FinOpsTag)} —
 *       same shape as publish; records subscribe-side message/byte attribution.</li>
 * </ul>
 *
 * <h2>USD cost formula</h2>
 * <pre>
 *   estimatedCostUsd = totalBytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB
 * </pre>
 *
 * <p>Pub/Sub charges per TiB of message throughput (1 TiB = 2<sup>40</sup>
 * bytes = {@value #BYTES_PER_TIB}). The first 10 GiB/month is free; this
 * tracker records gross cost (i.e., no free-tier deduction). Source:
 * <a href="https://cloud.google.com/pubsub/pricing">
 *     Pub/Sub pricing</a>
 *
 * <p>The {@code messageCount} parameter is recorded in
 * {@link CostMetrics#billedMessagesCount()} for attribution; it does not
 * contribute to the USD estimate because Pub/Sub does not charge
 * per-message in isolation (throughput-bytes drives the bill).
 *
 * <h2>Zero / negative input</h2>
 * <p>Zero or negative counts/bytes are accepted; cost will be zero and a
 * {@code WARN} log is emitted. {@link FinOpsSink#record} is still called
 * once so every operation appears in the cost table.
 *
 * <h2>Construction</h2>
 * <p>Pass in a {@link FinOpsSink}. This class does NOT hold a Pub/Sub client —
 * it operates on message counts and byte counts already obtained by the caller.
 * No {@link AutoCloseable}.
 *
 * <p>Sprint-13 deliverable for issue #70 (T13.2).
 */
public final class PubSubCostTracker {

    private static final Logger LOG = LoggerFactory.getLogger(PubSubCostTracker.class);

    /**
     * Bytes in one tebibyte (2^40).
     *
     * <p>Pub/Sub pricing uses binary TiB. Mirrors
     * {@code BigQueryCostTracker.BYTES_PER_TIB} for consistency.
     * Use this constant — not 1e12 — to avoid an ~10% undercount.
     * Source: <a href="https://cloud.google.com/pubsub/pricing">
     *     Pub/Sub pricing</a>
     */
    public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

    /**
     * Pub/Sub message throughput cost in USD per TiB.
     *
     * <p>Rate as of 2025: $40.00/TiB of message data throughput.
     * The first 10 GiB per month is free; this constant represents the
     * on-demand rate above the free tier. Source:
     * <a href="https://cloud.google.com/pubsub/pricing">
     *     Pub/Sub pricing</a>
     *
     * <p><b>Note on issue #70 paraphrase</b>: the ticket text mentioned
     * "$0.04/MiB" which is approximately 1000× the actual per-TiB rate
     * ($40/TiB ≈ $0.000038/MiB). This constant uses the correct per-TiB
     * billing unit from the GCP pricing page.
     */
    public static final double THROUGHPUT_COST_USD_PER_TIB = 40.00;

    private final FinOpsSink sink;

    /**
     * Primary constructor.
     *
     * @param sink FinOps sink that receives the built {@link CostMetrics}. Required.
     * @throws NullPointerException if {@code sink} is null.
     */
    public PubSubCostTracker(FinOpsSink sink) {
        this.sink = Objects.requireNonNull(sink, "sink must not be null");
    }

    /**
     * Record cost metrics for a Pub/Sub publish batch and emit them via the sink.
     *
     * <p>Maps {@code messageCount} → {@code billedMessagesCount} and
     * {@code totalBytes} → {@code billedBytesWritten}. Estimates USD from
     * {@code totalBytes} using {@link #THROUGHPUT_COST_USD_PER_TIB}. Zero or
     * negative inputs log at WARN and record zero cost; {@link FinOpsSink#record}
     * is called exactly once.
     *
     * @param messageCount Number of messages published.
     * @param totalBytes   Total payload bytes published (including message overhead).
     * @param runId        Pipeline run identifier.
     * @param tag          FinOps attribution tag.
     * @throws NullPointerException if {@code runId} or {@code tag} is null.
     */
    public void trackPublish(long messageCount, long totalBytes, String runId, FinOpsTag tag) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tag, "tag must not be null");

        if (messageCount <= 0L) {
            LOG.warn("PubSubCostTracker.trackPublish: messageCount={} for runId={} — recording zero messages",
                    messageCount, runId);
        }
        if (totalBytes <= 0L) {
            LOG.warn("PubSubCostTracker.trackPublish: totalBytes={} for runId={} — recording zero cost",
                    totalBytes, runId);
        }

        long messages = Math.max(0L, messageCount);
        long bytes = Math.max(0L, totalBytes);
        double costUsd = bytesToUsd(bytes);

        CostMetrics metrics = CostMetrics.builder(runId)
                .billedMessagesCount(messages)
                .billedBytesWritten(bytes)
                .estimatedCostUsd(costUsd)
                .build();

        sink.record(metrics, tag);
    }

    /**
     * Record cost metrics for a Pub/Sub subscription pull/push batch and emit
     * them via the sink.
     *
     * <p>Mirrors {@link #trackPublish} in shape: maps {@code messageCount} →
     * {@code billedMessagesCount} and {@code totalBytes} → {@code billedBytesWritten};
     * estimates USD from {@code totalBytes}. Pub/Sub charges both publisher
     * and subscriber throughput, so the same formula and rate apply.
     * Zero or negative inputs log at WARN; {@link FinOpsSink#record} is called
     * exactly once.
     *
     * @param messageCount Number of messages received.
     * @param totalBytes   Total payload bytes received.
     * @param runId        Pipeline run identifier.
     * @param tag          FinOps attribution tag.
     * @throws NullPointerException if {@code runId} or {@code tag} is null.
     */
    public void trackSubscribe(long messageCount, long totalBytes, String runId, FinOpsTag tag) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tag, "tag must not be null");

        if (messageCount <= 0L) {
            LOG.warn("PubSubCostTracker.trackSubscribe: messageCount={} for runId={} — recording zero messages",
                    messageCount, runId);
        }
        if (totalBytes <= 0L) {
            LOG.warn("PubSubCostTracker.trackSubscribe: totalBytes={} for runId={} — recording zero cost",
                    totalBytes, runId);
        }

        long messages = Math.max(0L, messageCount);
        long bytes = Math.max(0L, totalBytes);
        double costUsd = bytesToUsd(bytes);

        CostMetrics metrics = CostMetrics.builder(runId)
                .billedMessagesCount(messages)
                .billedBytesWritten(bytes)
                .estimatedCostUsd(costUsd)
                .build();

        sink.record(metrics, tag);
    }

    // --- private helpers ----------------------------------------------------

    /** Convert bytes to USD using {@link #THROUGHPUT_COST_USD_PER_TIB}. */
    private static double bytesToUsd(long bytes) {
        if (bytes <= 0L) {
            return 0.0;
        }
        return (double) bytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;
    }
}
