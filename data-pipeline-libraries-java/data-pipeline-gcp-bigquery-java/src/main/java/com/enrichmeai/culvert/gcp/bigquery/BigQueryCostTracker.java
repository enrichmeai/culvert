package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics;
import com.google.cloud.bigquery.JobStatistics.LoadStatistics;
import com.google.cloud.bigquery.JobStatistics.QueryStatistics;
import com.google.cloud.bigquery.QueryJobConfiguration;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Objects;

/**
 * Reads {@link JobStatistics} from a completed BigQuery {@link Job}, builds a
 * {@link CostMetrics} record, and pushes it to the {@link FinOpsSink}.
 *
 * <h2>Supported job types</h2>
 * <ul>
 *   <li><b>Query jobs</b>: {@link QueryStatistics#getTotalBytesBilled()} maps to
 *       {@code billedBytesScanned}; {@link JobStatistics#getTotalSlotMs()} maps
 *       to {@code slotMillis}.</li>
 *   <li><b>Load jobs</b>: {@link LoadStatistics#getOutputBytes()} maps to
 *       {@code billedBytesWritten}.</li>
 * </ul>
 *
 * <h2>USD cost formula — query jobs</h2>
 * <pre>
 *   estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB
 * </pre>
 *
 * <p>BigQuery on-demand pricing (as of 2025) charges
 * <b>${@value #QUERY_COST_USD_PER_TIB} per TiB scanned</b>, where 1 TiB = 2<sup>40</sup>
 * bytes (= {@value #BYTES_PER_TIB}). Source:
 * <a href="https://cloud.google.com/bigquery/pricing#on_demand_pricing">
 *     BigQuery on-demand pricing</a>. Batch loads are free to ingest; load cost
 * constant {@link #LOAD_COST_USD_PER_TIB} represents a GCS-egress-equivalent
 * accounting rate, not an actual BigQuery charge.
 *
 * <h2>Null statistics</h2>
 * <p>Any null statistics field is treated as zero and a {@code WARN} log is
 * emitted. A null {@link Job#getStatistics()} entirely skips emission and
 * logs at {@code WARN}.
 *
 * <h2>Dry-run pre-flight</h2>
 * <p>{@link #estimateDryRun(QueryJobConfiguration, String)} submits a
 * {@code setDryRun(true)} job so BigQuery validates + estimates without
 * executing. The Google Cloud SDK documents that dry-run jobs populate
 * {@link QueryStatistics#getTotalBytesBilled()} on supported configurations.
 * If {@code getTotalBytesBilled()} is null/zero (observed on some dry-run
 * responses), this method falls back to
 * {@link QueryStatistics#getTotalBytesProcessed()} and emits a WARN. The
 * fallback is required because dry-run semantics do not guarantee a billed
 * value — the field is defined as "bytes billed for a completed query"; on a
 * dry run the query never executes. This risk is flagged for architect review
 * via the emulator IT ({@code BigQueryCostTrackerIT}).
 *
 * <h2>Construction</h2>
 * <p>Pass in a pre-built {@link BigQuery} client and a {@link FinOpsSink}.
 * This class does NOT implement {@link AutoCloseable} — the BigQuery 2.x
 * client is not closeable.
 *
 * <p>Sprint-13 deliverable for issue #69 (T13.1). Sets the pattern for T13.2.
 */
public final class BigQueryCostTracker {

    private static final Logger LOG = LoggerFactory.getLogger(BigQueryCostTracker.class);

    /**
     * Bytes in one tebibyte (2^40).
     *
     * <p>BigQuery on-demand pricing uses the binary definition of terabyte.
     * Use this constant — not 1e12 — to avoid an ~10% undercount in estimates.
     * Source: <a href="https://cloud.google.com/bigquery/pricing#on_demand_pricing">
     *     BigQuery on-demand pricing</a>
     */
    public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

    /**
     * BigQuery on-demand query cost in USD per TiB scanned.
     *
     * <p>Rate as of 2025: $5.00/TiB for on-demand queries.
     * Source: <a href="https://cloud.google.com/bigquery/pricing#on_demand_pricing">
     *     BigQuery on-demand pricing</a>
     */
    public static final double QUERY_COST_USD_PER_TIB = 5.00;

    /**
     * Load cost constant in USD per TiB written — represents a GCS-egress-equivalent
     * rate for accounting purposes.
     *
     * <p><b>Note</b>: BigQuery batch loads are actually free to ingest.
     * This constant is an egress-equivalent placeholder used to attribute
     * the infrastructure cost of moving data into BigQuery. Teams may set this
     * to 0.0 if no GCS egress is charged in their network topology.
     * Source: <a href="https://cloud.google.com/bigquery/pricing#data_ingestion_pricing">
     *     BigQuery data ingestion pricing</a>
     */
    public static final double LOAD_COST_USD_PER_TIB = 0.01;

    private final BigQuery client;
    private final FinOpsSink sink;

    /**
     * Primary constructor.
     *
     * @param client Pre-built BigQuery client. Required.
     * @param sink   FinOps sink that receives the built {@link CostMetrics}. Required.
     * @throws NullPointerException if either argument is null.
     */
    public BigQueryCostTracker(BigQuery client, FinOpsSink sink) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.sink = Objects.requireNonNull(sink, "sink must not be null");
    }

    /**
     * Extract cost metrics from a completed BigQuery job and emit them via the sink.
     *
     * <p>For <b>query jobs</b>: reads {@link QueryStatistics#getTotalBytesBilled()}
     * → {@code billedBytesScanned} and {@link JobStatistics#getTotalSlotMs()}
     * → {@code slotMillis}; estimates USD using {@link #QUERY_COST_USD_PER_TIB}.
     *
     * <p>For <b>load jobs</b>: reads {@link LoadStatistics#getOutputBytes()}
     * → {@code billedBytesWritten}; estimates USD using {@link #LOAD_COST_USD_PER_TIB}.
     *
     * <p>Null statistics fields are treated as zero and logged at WARN.
     * If {@code job.getStatistics()} is null, no metrics are emitted.
     *
     * @param job   Completed BigQuery job. Required.
     * @param runId Pipeline run identifier to associate with the cost record. Required.
     * @param tag   FinOps attribution tag passed directly to the sink. Required.
     * @throws NullPointerException if job, runId, or tag is null.
     */
    public void trackJob(Job job, String runId, FinOpsTag tag) {
        Objects.requireNonNull(job, "job must not be null");
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tag, "tag must not be null");

        JobStatistics stats = job.getStatistics();
        if (stats == null) {
            LOG.warn("BigQueryCostTracker: job {} has null statistics — cost metrics not emitted",
                    job.getJobId());
            return;
        }

        CostMetrics metrics;
        if (stats instanceof QueryStatistics qs) {
            metrics = buildFromQueryStats(qs, stats, runId);
        } else if (stats instanceof LoadStatistics ls) {
            metrics = buildFromLoadStats(ls, runId);
        } else {
            // Copy / Extract / Script jobs — emit zero-cost record so the run
            // still appears in the cost table; slotMillis is on base JobStatistics.
            long slotMillis = safeSlotMs(stats, runId);
            metrics = CostMetrics.builder(runId)
                    .slotMillis(slotMillis)
                    .build();
        }

        sink.record(metrics, tag);
    }

    /**
     * Submit a dry-run job to obtain BigQuery's byte-estimate for a query
     * without executing it.
     *
     * <p>Reads {@link QueryStatistics#getTotalBytesBilled()}. If that field is
     * null or zero (dry-run semantics do not guarantee a billed value — the query
     * never executes, so no billing event occurs), falls back to
     * {@link QueryStatistics#getTotalBytesProcessed()} and emits a WARN. Cost
     * is estimated using {@link #QUERY_COST_USD_PER_TIB}.
     *
     * <p>All fields except {@code estimatedCostUsd} and {@code billedBytesScanned}
     * are zero — the record is a pre-flight estimate only.
     *
     * <p><b>Risk</b>: whether either bytes field is populated by the BigQuery
     * service on dry-run is a runtime guarantee; verify in the emulator IT
     * ({@code BigQueryCostTrackerIT}) before relying on this in production.
     *
     * @param config QueryJobConfiguration to estimate. Must not be dry-run already
     *               (this method forces dry-run internally).
     * @param runId  Pipeline run identifier for the returned CostMetrics. Required.
     * @return A CostMetrics with {@code estimatedCostUsd} and
     *         {@code billedBytesScanned} populated; all other fields zero.
     * @throws NullPointerException if config or runId is null.
     * @throws RuntimeException     wrapping InterruptedException if the dry-run
     *                              job wait is interrupted.
     */
    public CostMetrics estimateDryRun(QueryJobConfiguration config, String runId) {
        Objects.requireNonNull(config, "config must not be null");
        Objects.requireNonNull(runId, "runId must not be null");

        QueryJobConfiguration dryRunConfig = config.toBuilder()
                .setDryRun(true)
                .build();

        Job dryRunJob = client.create(JobInfo.of(dryRunConfig));

        // Dry-run jobs complete synchronously — the BigQuery API returns the
        // job with DONE status immediately without waiting. We call waitFor()
        // for correctness on the off-chance the API changes.
        Job completedJob;
        try {
            completedJob = dryRunJob.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery dry-run job interrupted for runId=" + runId, e);
        }

        if (completedJob == null) {
            LOG.warn("BigQueryCostTracker: dry-run job returned null for runId={} — returning zero estimate",
                    runId);
            return CostMetrics.zero(runId);
        }

        QueryStatistics qs = completedJob.getStatistics();
        if (qs == null) {
            LOG.warn("BigQueryCostTracker: dry-run job for runId={} returned null statistics — returning zero estimate",
                    runId);
            return CostMetrics.zero(runId);
        }

        long bytesScanned = resolveDryRunBytes(qs, runId);
        double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB);

        return CostMetrics.builder(runId)
                .billedBytesScanned(bytesScanned)
                .estimatedCostUsd(costUsd)
                .build();
    }

    // --- private helpers ----------------------------------------------------

    private CostMetrics buildFromQueryStats(QueryStatistics qs,
                                            JobStatistics baseStats,
                                            String runId) {
        long bytesScanned = safeBytesScanned(qs, runId);
        long slotMillis = safeSlotMs(baseStats, runId);
        double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB);

        return CostMetrics.builder(runId)
                .billedBytesScanned(bytesScanned)
                .slotMillis(slotMillis)
                .estimatedCostUsd(costUsd)
                .build();
    }

    private CostMetrics buildFromLoadStats(LoadStatistics ls, String runId) {
        long bytesWritten = safeOutputBytes(ls, runId);
        double costUsd = bytesToUsd(bytesWritten, LOAD_COST_USD_PER_TIB);

        return CostMetrics.builder(runId)
                .billedBytesWritten(bytesWritten)
                .estimatedCostUsd(costUsd)
                .build();
    }

    /** Extract getTotalBytesBilled, treating null as zero + WARN. */
    private static long safeBytesScanned(QueryStatistics qs, String runId) {
        Long v = qs.getTotalBytesBilled();
        if (v == null) {
            LOG.warn("BigQueryCostTracker: getTotalBytesBilled() is null for runId={} — treating as 0",
                    runId);
            return 0L;
        }
        return v;
    }

    /** Extract getTotalSlotMs from base JobStatistics, treating null as zero + WARN. */
    private static long safeSlotMs(JobStatistics stats, String runId) {
        Long v = stats.getTotalSlotMs();
        if (v == null) {
            LOG.warn("BigQueryCostTracker: getTotalSlotMs() is null for runId={} — treating as 0",
                    runId);
            return 0L;
        }
        return v;
    }

    /** Extract getOutputBytes from LoadStatistics, treating null as zero + WARN. */
    private static long safeOutputBytes(LoadStatistics ls, String runId) {
        Long v = ls.getOutputBytes();
        if (v == null) {
            LOG.warn("BigQueryCostTracker: getOutputBytes() is null for runId={} — treating as 0",
                    runId);
            return 0L;
        }
        return v;
    }

    /**
     * Resolve bytes for dry-run cost estimate.
     *
     * <p>Tries {@link QueryStatistics#getTotalBytesBilled()} first; falls back
     * to {@link QueryStatistics#getTotalBytesProcessed()} if billed is null or
     * zero (dry-run jobs don't incur a billing event, so the billed field may
     * be absent). See class-level Javadoc for the runtime verification risk.
     */
    private static long resolveDryRunBytes(QueryStatistics qs, String runId) {
        Long billed = qs.getTotalBytesBilled();
        if (billed != null && billed > 0L) {
            return billed;
        }
        // Fall back to getTotalBytesProcessed() which dry-run does populate.
        Long processed = qs.getTotalBytesProcessed();
        if (processed != null && processed > 0L) {
            LOG.warn("BigQueryCostTracker: getTotalBytesBilled() null/zero on dry-run for "
                    + "runId={} — falling back to getTotalBytesProcessed()={}", runId, processed);
            return processed;
        }
        LOG.warn("BigQueryCostTracker: both getTotalBytesBilled() and getTotalBytesProcessed() "
                + "are null/zero on dry-run for runId={} — returning zero estimate", runId);
        return 0L;
    }

    /** Convert bytes to USD using the given per-TiB rate. */
    private static double bytesToUsd(long bytes, double costPerTib) {
        if (bytes <= 0L) {
            return 0.0;
        }
        return (double) bytes / (double) BYTES_PER_TIB * costPerTib;
    }
}
