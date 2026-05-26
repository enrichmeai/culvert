package com.enrichmeai.culvert.finops;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Cost metrics for a single operation (a query, a load, an upload).
 *
 * <p>All numeric fields default to zero so the same record can be used for
 * operations that don't fill every dimension (a GCS upload populates
 * {@code billedBytesWritten} but not {@code slotMillis}). The fields cover
 * BigQuery slot-millis, scanned/written bytes, GCS storage bytes, and
 * Pub/Sub message counts — but the record itself is generic. AWS Redshift
 * slot equivalents (or Azure DWUs) populate the same fields; the
 * cloud-specific cost-tracker decides how each metric maps.
 *
 * <p>Mirrors the Python {@code CostMetrics} dataclass.
 *
 * @param runId               The pipeline run that incurred the cost.
 * @param estimatedCostUsd    Estimated cost in USD.
 * @param billedBytesScanned  BigQuery: bytes scanned by a query.
 * @param billedBytesWritten  Bytes written (table loads, GCS uploads).
 * @param billedBytesStored   Bytes stored (GCS storage class * duration).
 * @param billedMessagesCount Pub/Sub messages (or equivalent on other clouds).
 * @param slotMillis          BigQuery slot usage in slot-milliseconds.
 * @param computeUnits        Normalised compute units (warehouse-specific).
 * @param labels              Resource labels at the time of the operation.
 * @param timestamp           When the cost was recorded.
 */
public record CostMetrics(
        String runId,
        double estimatedCostUsd,
        long billedBytesScanned,
        long billedBytesWritten,
        long billedBytesStored,
        long billedMessagesCount,
        long slotMillis,
        double computeUnits,
        Map<String, String> labels,
        Instant timestamp) {

    public CostMetrics {
        Objects.requireNonNull(runId, "runId");
        Objects.requireNonNull(timestamp, "timestamp");
        if (labels == null) {
            labels = Map.of();
        } else {
            labels = Map.copyOf(labels);
        }
    }

    /** Zero-valued metrics with just the runId and the current timestamp. */
    public static CostMetrics zero(String runId) {
        return new CostMetrics(runId, 0.0, 0L, 0L, 0L, 0L, 0L, 0.0,
                Map.of(), Instant.now());
    }

    public static Builder builder(String runId) {
        return new Builder(runId);
    }

    public static final class Builder {
        private final String runId;
        private double estimatedCostUsd;
        private long billedBytesScanned;
        private long billedBytesWritten;
        private long billedBytesStored;
        private long billedMessagesCount;
        private long slotMillis;
        private double computeUnits;
        private Map<String, String> labels = new HashMap<>();
        private Instant timestamp = Instant.now();

        private Builder(String runId) {
            this.runId = runId;
        }

        public Builder estimatedCostUsd(double v) { this.estimatedCostUsd = v; return this; }
        public Builder billedBytesScanned(long v) { this.billedBytesScanned = v; return this; }
        public Builder billedBytesWritten(long v) { this.billedBytesWritten = v; return this; }
        public Builder billedBytesStored(long v) { this.billedBytesStored = v; return this; }
        public Builder billedMessagesCount(long v) { this.billedMessagesCount = v; return this; }
        public Builder slotMillis(long v) { this.slotMillis = v; return this; }
        public Builder computeUnits(double v) { this.computeUnits = v; return this; }
        public Builder labels(Map<String, String> v) { this.labels = v; return this; }
        public Builder timestamp(Instant v) { this.timestamp = v; return this; }

        public CostMetrics build() {
            return new CostMetrics(runId, estimatedCostUsd, billedBytesScanned,
                    billedBytesWritten, billedBytesStored, billedMessagesCount,
                    slotMillis, computeUnits, labels, timestamp);
        }
    }
}
