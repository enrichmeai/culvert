package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Objects;

/**
 * Builds a {@link CostMetrics} record from GCS operation sizes and pushes it
 * to the {@link FinOpsSink}.
 *
 * <h2>Supported operations</h2>
 * <ul>
 *   <li><b>Upload</b>: {@link #trackUpload(long, String, FinOpsTag)} — records
 *       {@code billedBytesWritten} from the bytes written; estimates USD using
 *       {@link #WRITE_COST_USD_PER_GIB}.</li>
 *   <li><b>Storage class</b>: {@link #trackStorageClass(long, String, String, FinOpsTag)} —
 *       records {@code billedBytesStored}; estimates monthly storage cost using
 *       per-class rates (Standard / Nearline / Coldline / Archive).</li>
 * </ul>
 *
 * <h2>USD cost formula — upload</h2>
 * <pre>
 *   estimatedCostUsd = bytesWritten / BYTES_PER_GIB * WRITE_COST_USD_PER_GIB
 * </pre>
 *
 * <p><b>Note</b>: GCS does not charge per-byte for writes (it charges per
 * Class A operation). {@link #WRITE_COST_USD_PER_GIB} is an accounting
 * placeholder analogous to {@code BigQueryCostTracker.LOAD_COST_USD_PER_TIB}.
 * Teams may set the effective rate to 0.0 if they do not need per-upload cost
 * attribution. Source:
 * <a href="https://cloud.google.com/storage/pricing#operations-pricing">
 *     GCS operations pricing</a>
 *
 * <h2>USD cost formula — storage class</h2>
 * <pre>
 *   estimatedCostUsd = bytesStored / BYTES_PER_GIB * rateForClass
 * </pre>
 *
 * <p>Rates are per-GiB-month (1 GiB = 2<sup>30</sup> bytes = {@value #BYTES_PER_GIB}).
 * Source:
 * <a href="https://cloud.google.com/storage/pricing#storage-pricing">
 *     GCS storage pricing</a>
 *
 * <h2>Zero / negative input</h2>
 * <p>Zero or negative byte counts are accepted; cost will be zero and a
 * {@code WARN} log is emitted. {@link FinOpsSink#record} is still called
 * once so every operation appears in the cost table.
 *
 * <h2>Unknown storage class</h2>
 * <p>An unrecognised {@code storageClass} string falls back to the Standard
 * rate and logs at {@code WARN}.
 *
 * <h2>Construction</h2>
 * <p>Pass in a {@link FinOpsSink}. This class does NOT hold a GCS
 * client — it operates on byte counts already obtained by the caller
 * (typically from a GCS API response). No {@link AutoCloseable}.
 *
 * <p>Sprint-13 deliverable for issue #70 (T13.2).
 */
public final class GcsCostTracker {

    private static final Logger LOG = LoggerFactory.getLogger(GcsCostTracker.class);

    /**
     * Bytes in one gibibyte (2^30).
     *
     * <p>GCS storage pricing is quoted in GiB-months (binary definition).
     * Use this constant — not 1e9 — to avoid an ~7% undercount. Mirrors the
     * binary convention in {@code BigQueryCostTracker.BYTES_PER_TIB} (2^40).
     * Source: <a href="https://cloud.google.com/storage/pricing#storage-pricing">
     *     GCS storage pricing</a>
     */
    public static final long BYTES_PER_GIB = 1_073_741_824L; // 2^30

    /**
     * GCS upload cost accounting placeholder in USD per GiB written.
     *
     * <p><b>Note</b>: GCS does not bill per-byte for write operations.
     * Actual Class A operation pricing is per-10,000 operations.
     * This constant is an accounting placeholder used to attribute the
     * infrastructure cost of uploading data. Teams may set this to 0.0
     * if per-upload cost attribution is not needed.
     * Source: <a href="https://cloud.google.com/storage/pricing#operations-pricing">
     *     GCS operations pricing</a>
     */
    public static final double WRITE_COST_USD_PER_GIB = 0.01;

    /**
     * GCS Standard storage rate in USD per GiB-month (US multi-region, 2025).
     *
     * <p>Rate: $0.020/GiB-month.
     * Source: <a href="https://cloud.google.com/storage/pricing#storage-pricing">
     *     GCS storage pricing</a>
     */
    public static final double STANDARD_STORAGE_USD_PER_GIB = 0.020;

    /**
     * GCS Nearline storage rate in USD per GiB-month (US multi-region, 2025).
     *
     * <p>Rate: $0.010/GiB-month.
     * Source: <a href="https://cloud.google.com/storage/pricing#storage-pricing">
     *     GCS storage pricing</a>
     */
    public static final double NEARLINE_STORAGE_USD_PER_GIB = 0.010;

    /**
     * GCS Coldline storage rate in USD per GiB-month (US multi-region, 2025).
     *
     * <p>Rate: $0.004/GiB-month.
     * Source: <a href="https://cloud.google.com/storage/pricing#storage-pricing">
     *     GCS storage pricing</a>
     */
    public static final double COLDLINE_STORAGE_USD_PER_GIB = 0.004;

    /**
     * GCS Archive storage rate in USD per GiB-month (US multi-region, 2025).
     *
     * <p>Rate: $0.0012/GiB-month.
     * Source: <a href="https://cloud.google.com/storage/pricing#storage-pricing">
     *     GCS storage pricing</a>
     */
    public static final double ARCHIVE_STORAGE_USD_PER_GIB = 0.0012;

    private final FinOpsSink sink;

    /**
     * Primary constructor.
     *
     * @param sink FinOps sink that receives the built {@link CostMetrics}. Required.
     * @throws NullPointerException if {@code sink} is null.
     */
    public GcsCostTracker(FinOpsSink sink) {
        this.sink = Objects.requireNonNull(sink, "sink must not be null");
    }

    /**
     * Record cost metrics for a GCS upload operation and emit them via the sink.
     *
     * <p>Maps {@code bytesWritten} → {@code billedBytesWritten} and estimates
     * USD using {@link #WRITE_COST_USD_PER_GIB}. If {@code bytesWritten} is
     * zero or negative, a {@code WARN} log is emitted and cost is recorded as
     * zero. {@link FinOpsSink#record} is called exactly once.
     *
     * @param bytesWritten Number of bytes written in the upload operation.
     * @param runId        Pipeline run identifier to associate with the cost record.
     * @param tag          FinOps attribution tag passed directly to the sink.
     * @throws NullPointerException if {@code runId} or {@code tag} is null.
     */
    public void trackUpload(long bytesWritten, String runId, FinOpsTag tag) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tag, "tag must not be null");

        if (bytesWritten <= 0L) {
            LOG.warn("GcsCostTracker.trackUpload: bytesWritten={} for runId={} — recording zero cost",
                    bytesWritten, runId);
        }

        long bytes = Math.max(0L, bytesWritten);
        double costUsd = bytesToUsd(bytes, WRITE_COST_USD_PER_GIB);

        CostMetrics metrics = CostMetrics.builder(runId)
                .billedBytesWritten(bytes)
                .estimatedCostUsd(costUsd)
                .build();

        sink.record(metrics, tag);
    }

    /**
     * Record cost metrics for bytes stored under a given GCS storage class and
     * emit them via the sink.
     *
     * <p>Maps {@code bytesStored} → {@code billedBytesStored} and estimates
     * monthly storage USD using the per-class rate. Recognised storage class
     * strings (case-insensitive): {@code STANDARD}, {@code NEARLINE},
     * {@code COLDLINE}, {@code ARCHIVE}. An unrecognised class falls back to
     * the Standard rate and a {@code WARN} log is emitted.
     *
     * <p>If {@code bytesStored} is zero or negative, a {@code WARN} is emitted
     * and cost is recorded as zero. {@link FinOpsSink#record} is called exactly
     * once.
     *
     * @param bytesStored  Number of bytes stored.
     * @param storageClass GCS storage class name (e.g. {@code "STANDARD"}).
     *                     Case-insensitive. Null is treated as unknown and falls
     *                     back to Standard.
     * @param runId        Pipeline run identifier.
     * @param tag          FinOps attribution tag.
     * @throws NullPointerException if {@code runId} or {@code tag} is null.
     */
    public void trackStorageClass(long bytesStored, String storageClass,
                                   String runId, FinOpsTag tag) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tag, "tag must not be null");

        if (bytesStored <= 0L) {
            LOG.warn("GcsCostTracker.trackStorageClass: bytesStored={} for runId={} — recording zero cost",
                    bytesStored, runId);
        }

        double rate = resolveStorageRate(storageClass, runId);
        long bytes = Math.max(0L, bytesStored);
        double costUsd = bytesToUsd(bytes, rate);

        CostMetrics metrics = CostMetrics.builder(runId)
                .billedBytesStored(bytes)
                .estimatedCostUsd(costUsd)
                .build();

        sink.record(metrics, tag);
    }

    // --- private helpers ----------------------------------------------------

    /**
     * Resolve the per-GiB monthly storage rate for the given storage class.
     * Falls back to {@link #STANDARD_STORAGE_USD_PER_GIB} and logs WARN on
     * unknown/null input.
     */
    private static double resolveStorageRate(String storageClass, String runId) {
        if (storageClass == null) {
            LOG.warn("GcsCostTracker.trackStorageClass: null storageClass for runId={} — defaulting to STANDARD rate",
                    runId);
            return STANDARD_STORAGE_USD_PER_GIB;
        }
        return switch (storageClass.toUpperCase()) {
            case "STANDARD"  -> STANDARD_STORAGE_USD_PER_GIB;
            case "NEARLINE"  -> NEARLINE_STORAGE_USD_PER_GIB;
            case "COLDLINE"  -> COLDLINE_STORAGE_USD_PER_GIB;
            case "ARCHIVE"   -> ARCHIVE_STORAGE_USD_PER_GIB;
            default -> {
                LOG.warn("GcsCostTracker.trackStorageClass: unknown storageClass='{}' for runId={} "
                        + "— defaulting to STANDARD rate", storageClass, runId);
                yield STANDARD_STORAGE_USD_PER_GIB;
            }
        };
    }

    /** Convert bytes to USD using the given per-GiB rate. */
    private static double bytesToUsd(long bytes, double ratePerGib) {
        if (bytes <= 0L) {
            return 0.0;
        }
        return (double) bytes / (double) BYTES_PER_GIB * ratePerGib;
    }
}
