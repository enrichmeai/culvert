package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.CopyJobConfiguration;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.FormatOptions;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics.LoadStatistics;
import com.google.cloud.bigquery.LoadJobConfiguration;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryParameterValue;
import com.google.cloud.bigquery.Schema;
import com.google.cloud.bigquery.StandardSQLTypeName;
import com.google.cloud.bigquery.Table;
import com.google.cloud.bigquery.TableId;
import com.google.cloud.bigquery.TableResult;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * {@link Warehouse} implementation backed by Google Cloud BigQuery.
 *
 * <p>Wraps a {@link BigQuery} client. All operations are issued as BigQuery
 * jobs; the wrapped client is reused for every call. Fully-qualified table
 * names follow BigQuery's {@code project.dataset.table} convention; the
 * project component is optional and falls back to the warehouse's configured
 * {@code projectId} when omitted.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #BigQueryWarehouse(String, BigQuery)} — primary constructor,
 *       takes a pre-built client. Mirror of the pilot
 *       {@code SecretManagerProvider(projectId, client)} shape.</li>
 * </ul>
 *
 * <p>No no-arg constructor: a {@link BigQuery} client is not derivable from
 * a small bag of environment variables (project + location + credentials at
 * minimum), so {@link java.util.ServiceLoader} discovery via the META-INF
 * registration is reserved for sprint-4 auto-config wiring. The META-INF
 * services file is still pre-registered so that future wiring can claim it
 * without a re-release.
 *
 * <p>BigQuery dataset {@code location} (region) is configured on the
 * injected client via
 * {@link com.google.cloud.bigquery.BigQueryOptions.Builder#setLocation(String)}.
 * It is not a constructor argument here.
 *
 * <p>The wrapped {@link BigQuery} client is intentionally NOT closed by this
 * adapter — the google-cloud-bigquery 2.x client does not implement
 * {@link AutoCloseable}. The client manages its own gRPC channel lifecycle;
 * consumers that need explicit teardown should close the client they
 * injected. The pilot's AutoCloseable pattern (see
 * {@code SecretManagerProvider}) applies only to clients that themselves
 * implement {@code AutoCloseable}.
 *
 * <p>Sprint-1 deliverable for issue #6.
 */
public final class BigQueryWarehouse implements Warehouse {

    private final String projectId;
    private final BigQuery client;

    /**
     * Primary constructor. Mirrors the pilot's
     * {@code SecretManagerProvider(projectId, client)} arg-order convention.
     *
     * @param projectId GCP project ID for resolving unqualified table names.
     *                  Required.
     * @param client    Pre-built BigQuery client. Required. Ownership
     *                  transfers to this warehouse — {@link #close()} will
     *                  close it.
     * @throws NullPointerException if either argument is null.
     */
    public BigQueryWarehouse(String projectId, BigQuery client) {
        this.projectId = Objects.requireNonNull(projectId, "projectId must not be null");
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    /**
     * No-arg constructor for worker-side auto-config reconstruction.
     *
     * <p>When the pipeline's {@code RuntimeContext} crosses to a Beam worker its
     * adapter registry is rebuilt via {@code ServiceLoader}, which needs a
     * no-arg constructor. Project and dataset region come from the worker
     * environment ({@code GCP_PROJECT}/{@code GCP_LOCATION}) via
     * {@link BigQueryDefaults}; the BigQuery client is the Application Default
     * one (the worker runs as the pipeline's service account). Explicit
     * driver-side {@code new BigQueryWarehouse(project, client)} is preferred
     * where a specific client is required.
     */
    public BigQueryWarehouse() {
        this(BigQueryDefaults.project(), BigQueryDefaults.client());
    }

    @Override
    public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
        Objects.requireNonNull(sql, "sql must not be null");
        QueryJobConfiguration config = buildQueryConfig(sql, params);
        TableResult result;
        try {
            result = client.query(config);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery query interrupted", e);
        }
        return streamRows(result);
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        Objects.requireNonNull(sql, "sql must not be null");
        QueryJobConfiguration config = buildQueryConfig(sql, params);
        try {
            client.query(config);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery execute interrupted", e);
        }
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
        Objects.requireNonNull(uri, "uri must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
        Objects.requireNonNull(schema, "schema must not be null");

        TableId tableId = parseFqtn(targetTable);
        Schema bqSchema = toBigQuerySchema(schema);
        FormatOptions format = guessFormat(uri);

        LoadJobConfiguration loadConfig = LoadJobConfiguration.newBuilder(tableId, uri)
                .setSchema(bqSchema)
                .setFormatOptions(format)
                .build();

        Job job = client.create(JobInfo.of(loadConfig));
        Job completed = waitFor(job);
        LoadStatistics stats = completed.getStatistics();
        Long outputRows = stats.getOutputRows();
        return outputRows == null ? 0L : outputRows;
    }

    @Override
    public long merge(String sourceTable, String targetTable, List<String> keys) {
        Objects.requireNonNull(sourceTable, "sourceTable must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
        Objects.requireNonNull(keys, "keys must not be null");
        if (keys.isEmpty()) {
            throw new IllegalArgumentException("merge requires at least one key column");
        }
        // BigQuery's MERGE syntax requires explicit non-key column lists in
        // `WHEN MATCHED THEN UPDATE SET ...`; `SET t.* = s.*` is not valid.
        // Generating the column list requires a schema lookup against the
        // source table, which expands this method's responsibility beyond
        // sprint-1's "match the pilot's adaptation patterns" rule. Reserve
        // column-aware MERGE for sprint-4 follow-up; callers that need it
        // today can issue the MERGE via `execute(sql, params)` directly.
        throw new UnsupportedOperationException(
                "merge() is sprint-4 scope (requires column-aware SQL generation). "
                        + "Use execute(String, Map) with an explicit MERGE statement until then. "
                        + "Tracked at https://github.com/enrichmeai/gcp-pipeline-reference/issues/6");
    }

    @Override
    public long copy(String sourceTable, String targetTable) {
        Objects.requireNonNull(sourceTable, "sourceTable must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");

        TableId sourceId = parseFqtn(sourceTable);
        TableId targetId = parseFqtn(targetTable);

        CopyJobConfiguration copyConfig = CopyJobConfiguration.newBuilder(targetId, sourceId).build();
        Job job = client.create(JobInfo.of(copyConfig));
        waitFor(job);

        // CopyStatistics doesn't expose a row count; report the target
        // table's row count post-copy. Metadata-only operation in BQ — this
        // is a cheap call.
        Table table = client.getTable(targetId);
        if (table == null || table.getNumRows() == null) {
            return 0L;
        }
        return table.getNumRows().longValueExact();
    }

    @Override
    public boolean tableExists(String fqtn) {
        Objects.requireNonNull(fqtn, "fqtn must not be null");
        TableId tableId = parseFqtn(fqtn);
        try {
            // BigQuery's getTable() returns a non-null Table only when the
            // table exists; an explicit follow-up table.exists() roundtrip
            // would just repeat the check.
            return client.getTable(tableId) != null;
        } catch (BigQueryException e) {
            if (e.getCode() == 404) {
                return false;
            }
            throw e;
        }
    }

    // --- helpers -----------------------------------------------------------

    private QueryJobConfiguration buildQueryConfig(String sql, Map<String, Object> params) {
        QueryJobConfiguration.Builder builder = QueryJobConfiguration.newBuilder(sql);
        if (params != null) {
            for (Map.Entry<String, Object> entry : params.entrySet()) {
                builder.addNamedParameter(entry.getKey(), toParameterValue(entry.getValue()));
            }
        }
        return builder.build();
    }

    private static QueryParameterValue toParameterValue(Object value) {
        if (value == null) {
            return QueryParameterValue.of(null, StandardSQLTypeName.STRING);
        }
        if (value instanceof String s) {
            return QueryParameterValue.string(s);
        }
        if (value instanceof Long l) {
            return QueryParameterValue.int64(l);
        }
        if (value instanceof Integer i) {
            return QueryParameterValue.int64(i.longValue());
        }
        if (value instanceof Double d) {
            return QueryParameterValue.float64(d);
        }
        if (value instanceof Float f) {
            return QueryParameterValue.float64(f.doubleValue());
        }
        if (value instanceof Boolean b) {
            return QueryParameterValue.bool(b);
        }
        throw new IllegalArgumentException(
                "Unsupported parameter type for BigQuery binding: "
                        + value.getClass().getName()
                        + " (supported: String, Long, Integer, Double, Float, Boolean)");
    }

    private Iterator<Map<String, Object>> streamRows(TableResult result) {
        if (result == null) {
            return Collections.emptyIterator();
        }
        Schema schema = result.getSchema();
        List<String> fieldNames;
        if (schema == null) {
            fieldNames = List.of();
        } else {
            fieldNames = schema.getFields().stream()
                    .map(Field::getName)
                    .collect(Collectors.toUnmodifiableList());
        }
        Iterator<FieldValueList> source = result.iterateAll().iterator();
        return new Iterator<>() {
            @Override
            public boolean hasNext() {
                return source.hasNext();
            }

            @Override
            public Map<String, Object> next() {
                FieldValueList row = source.next();
                Map<String, Object> map = new LinkedHashMap<>(fieldNames.size() * 2);
                for (int i = 0; i < fieldNames.size(); i++) {
                    Object value = row.get(i).isNull() ? null : row.get(i).getValue();
                    map.put(fieldNames.get(i), value);
                }
                return map;
            }
        };
    }

    /**
     * Parse a fully-qualified table name. Accepts {@code project.dataset.table}
     * or {@code dataset.table} (project defaults to the warehouse's
     * configured {@link #projectId}).
     */
    private TableId parseFqtn(String fqtn) {
        String[] parts = fqtn.split("\\.");
        if (parts.length == 3) {
            return TableId.of(parts[0], parts[1], parts[2]);
        }
        if (parts.length == 2) {
            return TableId.of(projectId, parts[0], parts[1]);
        }
        throw new IllegalArgumentException(
                "Invalid BigQuery fqtn (expected 'project.dataset.table' or 'dataset.table'): "
                        + fqtn);
    }

    private static Schema toBigQuerySchema(EntitySchema schema) {
        List<Field> bqFields = new ArrayList<>(schema.fields().size());
        for (SchemaField sf : schema.fields()) {
            StandardSQLTypeName type = mapSqlType(sf.type());
            Field.Mode mode = mapMode(sf.mode());
            Field.Builder fb = Field.newBuilder(sf.name(), type).setMode(mode);
            sf.description().ifPresent(fb::setDescription);
            bqFields.add(fb.build());
        }
        return Schema.of(bqFields);
    }

    private static StandardSQLTypeName mapSqlType(String type) {
        // The contract uses BigQuery's vocabulary (STRING, INT64, ...) but
        // the values are warehouse-neutral, so accept common aliases too.
        String t = type.toUpperCase(Locale.ROOT);
        return switch (t) {
            case "STRING", "VARCHAR", "TEXT" -> StandardSQLTypeName.STRING;
            case "INT64", "INTEGER", "INT", "BIGINT" -> StandardSQLTypeName.INT64;
            case "FLOAT64", "FLOAT", "DOUBLE" -> StandardSQLTypeName.FLOAT64;
            case "BOOL", "BOOLEAN" -> StandardSQLTypeName.BOOL;
            case "DATE" -> StandardSQLTypeName.DATE;
            case "DATETIME" -> StandardSQLTypeName.DATETIME;
            case "TIMESTAMP" -> StandardSQLTypeName.TIMESTAMP;
            case "NUMERIC" -> StandardSQLTypeName.NUMERIC;
            case "BIGNUMERIC" -> StandardSQLTypeName.BIGNUMERIC;
            case "BYTES" -> StandardSQLTypeName.BYTES;
            case "JSON" -> StandardSQLTypeName.JSON;
            default -> throw new IllegalArgumentException(
                    "Unsupported schema field type for BigQuery: " + type);
        };
    }

    private static Field.Mode mapMode(String mode) {
        return switch (mode.toUpperCase(Locale.ROOT)) {
            case "REQUIRED" -> Field.Mode.REQUIRED;
            case "REPEATED" -> Field.Mode.REPEATED;
            default -> Field.Mode.NULLABLE;
        };
    }

    private static FormatOptions guessFormat(String uri) {
        String lower = uri.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".csv") || lower.endsWith(".csv.gz")) {
            return FormatOptions.csv();
        }
        if (lower.endsWith(".parquet")) {
            return FormatOptions.parquet();
        }
        if (lower.endsWith(".avro")) {
            return FormatOptions.avro();
        }
        if (lower.endsWith(".orc")) {
            return FormatOptions.orc();
        }
        // Newline-delimited JSON is BigQuery's default text load format and a
        // safe fallback for unknown extensions.
        return FormatOptions.json();
    }

    private static Job waitFor(Job job) {
        if (job == null) {
            throw new IllegalStateException("BigQuery returned a null Job; check ADC / quota");
        }
        Job completed;
        try {
            completed = job.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("BigQuery job interrupted", e);
        }
        if (completed == null) {
            // job.waitFor() returns null if the job no longer exists by the
            // time the wait completes. Map that to NoSuchElementException so
            // callers can distinguish missing-job from BigQuery errors.
            throw new NoSuchElementException(
                    "BigQuery job " + job.getJobId() + " disappeared before completion");
        }
        if (completed.getStatus() != null && completed.getStatus().getError() != null) {
            // Synthesise a BigQueryException from the BigQueryError carried
            // on the completed job's status. Use the (int code, String
            // message) ctor — the (List<BigQueryError>) overload is not on
            // every google-cloud-bigquery release inside the 2.x line. Code
            // 500 is a generic synthesised marker; the message preserves
            // the underlying reason for debugging.
            var err = completed.getStatus().getError();
            String msg = err.getMessage() != null ? err.getMessage() : err.toString();
            throw new BigQueryException(500, msg);
        }
        return completed;
    }
}
