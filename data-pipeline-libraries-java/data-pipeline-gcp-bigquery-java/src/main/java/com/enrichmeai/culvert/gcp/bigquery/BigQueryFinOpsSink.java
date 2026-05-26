package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryError;
import com.google.cloud.bigquery.InsertAllRequest;
import com.google.cloud.bigquery.InsertAllResponse;
import com.google.cloud.bigquery.TableId;

import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * {@link FinOpsSink} implementation backed by Google Cloud BigQuery streaming
 * inserts ({@code insertAll}).
 *
 * <p>Each {@link #record(CostMetrics, FinOpsTag)} call streams a single row
 * into the configured {@code cost_metrics} table. The row carries every field
 * from both {@link CostMetrics} and {@link FinOpsTag} flattened into the
 * table's columns; {@link CostMetrics#labels()} and
 * {@link FinOpsTag#extra()} flatten as {@code RECORD<key STRING, value STRING>}
 * arrays (BigQuery's only stable way to ship arbitrary map data without DDL
 * changes per row).
 *
 * <h2>Streaming buffer + cost</h2>
 *
 * <p>{@code insertAll} writes to BigQuery's streaming buffer. Rows are
 * queryable within seconds but are NOT immediately visible to
 * {@code COPY}/{@code EXPORT} jobs (streaming buffer flushes to managed
 * storage on BigQuery's schedule — usually within 90 minutes). Streaming
 * inserts also incur a per-GB cost on top of regular storage. For high-volume
 * cost emission, consider a load-job-based variant in a future sprint.
 *
 * <h2>Partial failures</h2>
 *
 * <p>{@code InsertAllResponse} can succeed at the request level while
 * reporting per-row errors. We treat any non-empty
 * {@link InsertAllResponse#getInsertErrors()} as a hard failure and throw
 * {@link FinOpsInsertException} — silently dropping cost rows would defeat
 * the FinOps audit trail.
 *
 * <h2>Construction</h2>
 *
 * <p>Pass in a pre-built {@link BigQuery} client, the GCP project ID, the
 * dataset, and the table name (default {@code cost_metrics} convention).
 * Like {@link BigQueryWarehouse} and {@link BigQueryJobControlRepository},
 * this class does NOT implement {@link AutoCloseable} — the BigQuery 2.x
 * client itself is not closeable.
 *
 * <p>Sprint-1 deliverable for issue #9.
 */
public final class BigQueryFinOpsSink implements FinOpsSink {

    /** Default table name when none specified. Matches the Python convention. */
    public static final String DEFAULT_TABLE = "cost_metrics";

    private static final DateTimeFormatter BQ_TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSSSSS");

    private final BigQuery client;
    private final TableId tableId;

    /**
     * Primary constructor.
     *
     * @param client    Pre-built BigQuery client. Required.
     * @param projectId GCP project ID. Required.
     * @param dataset   BigQuery dataset name. Required.
     * @param table     BigQuery table name. Required.
     * @throws NullPointerException if any argument is null.
     */
    public BigQueryFinOpsSink(BigQuery client, String projectId,
                              String dataset, String table) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        Objects.requireNonNull(projectId, "projectId must not be null");
        Objects.requireNonNull(dataset, "dataset must not be null");
        Objects.requireNonNull(table, "table must not be null");
        this.tableId = TableId.of(projectId, dataset, table);
    }

    // TODO sprint-4 auto-config: no-arg constructor reading GCP_PROJECT,
    // FINOPS_DATASET, FINOPS_TABLE. Skipped here because (client, projectId,
    // dataset, table) bootstrap exceeds the pilot's "no-arg only if <=2 env
    // vars" rule.

    @Override
    public void record(CostMetrics metrics, FinOpsTag tags) {
        Objects.requireNonNull(metrics, "metrics must not be null");
        Objects.requireNonNull(tags, "tags must not be null");

        InsertAllRequest request = InsertAllRequest.newBuilder(tableId)
                .addRow(toRow(metrics, tags))
                .build();

        InsertAllResponse response = client.insertAll(request);
        if (response.hasErrors()) {
            throw new FinOpsInsertException(metrics.runId(), response.getInsertErrors());
        }
    }

    /**
     * Build the wire row. Field naming convention: snake_case to match
     * BigQuery's idiomatic column naming.
     *
     * <p>Visible for testing — production callers should use
     * {@link #record(CostMetrics, FinOpsTag)}.
     */
    Map<String, Object> toRow(CostMetrics metrics, FinOpsTag tags) {
        Map<String, Object> row = new LinkedHashMap<>();
        // FinOpsTag attribution columns first — they're the cost-allocation key.
        row.put("system", tags.system());
        row.put("environment", tags.environment());
        row.put("cost_center", tags.costCenter());
        row.put("owner", tags.owner());
        // tags.runId() and metrics.runId() should match in practice; we ship
        // both and let the analyst spot any drift.
        row.put("tag_run_id", tags.runId());
        row.put("tag_extra", flattenMap(tags.extra()));

        // CostMetrics columns.
        row.put("run_id", metrics.runId());
        row.put("estimated_cost_usd", metrics.estimatedCostUsd());
        row.put("billed_bytes_scanned", metrics.billedBytesScanned());
        row.put("billed_bytes_written", metrics.billedBytesWritten());
        row.put("billed_bytes_stored", metrics.billedBytesStored());
        row.put("billed_messages_count", metrics.billedMessagesCount());
        row.put("slot_millis", metrics.slotMillis());
        row.put("compute_units", metrics.computeUnits());
        row.put("labels", flattenMap(metrics.labels()));

        // BigQuery TIMESTAMP wants either ISO-8601 or "yyyy-MM-dd HH:mm:ss.SSSSSS UTC";
        // ISO-8601 is widely accepted by insertAll JSON encoding.
        row.put("timestamp", metrics.timestamp().toString());

        return row;
    }

    /**
     * Flatten a {@code Map<String, String>} into a list of
     * {@code {"key": k, "value": v}} records — BigQuery's stable
     * representation for arbitrary-key map data without a schema update per
     * row.
     */
    private static List<Map<String, String>> flattenMap(Map<String, String> map) {
        if (map == null || map.isEmpty()) {
            return List.of();
        }
        List<Map<String, String>> out = new java.util.ArrayList<>(map.size());
        for (Map.Entry<String, String> e : map.entrySet()) {
            Map<String, String> entry = new LinkedHashMap<>(2);
            entry.put("key", e.getKey());
            entry.put("value", e.getValue());
            out.add(entry);
        }
        return out;
    }

    /**
     * Thrown when BigQuery's streaming insert returns per-row errors. The
     * underlying GCP {@link BigQueryError} list is preserved so callers can
     * report the specific row failures.
     */
    public static final class FinOpsInsertException extends RuntimeException {
        private static final long serialVersionUID = 1L;
        private final transient Map<Long, List<BigQueryError>> insertErrors;

        FinOpsInsertException(String runId, Map<Long, List<BigQueryError>> insertErrors) {
            super("BigQuery streaming insert returned errors for runId=" + runId
                    + " (" + insertErrors.size() + " row(s) failed)");
            this.insertErrors = insertErrors;
        }

        public Map<Long, List<BigQueryError>> getInsertErrors() {
            return insertErrors;
        }
    }
}
