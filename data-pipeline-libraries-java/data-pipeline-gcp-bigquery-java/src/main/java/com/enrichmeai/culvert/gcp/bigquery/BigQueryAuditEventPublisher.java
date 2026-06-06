package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.audit.AuditRecord;
import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryParameterValue;
import com.google.cloud.bigquery.TableId;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;

/**
 * {@link AuditEventPublisher} implementation backed by Google Cloud BigQuery.
 *
 * <p>Each {@link #publish(AuditRecord)} call writes a single audit row to a
 * configurable BigQuery audit table via a parameterised {@code INSERT ... VALUES}
 * DML statement ({@code client.query}). Using DML rather than {@code insertAll}
 * streaming inserts ensures compatibility with the
 * <a href="https://github.com/goccy/bigquery-emulator">goccy/bigquery-emulator</a>
 * used in integration tests, which does not support the streaming insert API.
 *
 * <p>{@link #flush()} is a no-op because every {@link #publish} call is
 * immediately written synchronously. The contract requires flush to be idempotent
 * and safe to call on an empty buffer — this implementation satisfies that.
 *
 * <h2>Failure isolation</h2>
 * <p>Any exception thrown during a {@link #publish} call is caught, logged at
 * {@code WARN} level, and swallowed. A pipeline audit failure must never
 * interrupt the data pipeline itself. The cumulative failure count is
 * accessible via {@link #auditFailureCount()} for tests and operational alerting.
 * The interrupt flag is preserved if an {@link InterruptedException} is involved.
 *
 * <h2>Audit table schema</h2>
 * <pre>{@code
 * CREATE TABLE `<project>.<dataset>.<table>` (
 *     run_id                        STRING  NOT NULL,
 *     pipeline_name                 STRING  NOT NULL,
 *     entity_type                   STRING  NOT NULL,
 *     source_file                   STRING  NOT NULL,
 *     record_count                  INT64   NOT NULL,
 *     processed_timestamp           TIMESTAMP NOT NULL,
 *     processing_duration_seconds   FLOAT64 NOT NULL,
 *     success                       BOOL    NOT NULL,
 *     error_count                   INT64   NOT NULL,
 *     audit_hash                    STRING,
 *     metadata_json                 STRING,
 *     published_at                  TIMESTAMP
 * );
 * }</pre>
 *
 * <p>{@code metadata} (a {@code Map<String,Object>}) is serialised to JSON and
 * stored in the {@code metadata_json} STRING column. This avoids the need for a
 * {@code ARRAY<STRUCT<key,value>>} schema and keeps the row fully emulator-compatible.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #BigQueryAuditEventPublisher()} — no-arg constructor for
 *       {@link java.util.ServiceLoader} discovery (T14.6). Resolves project-id
 *       from the three-step precedence chain:
 *       <ol>
 *         <li>System property {@value #SYSPROP_GCP_PROJECT}</li>
 *         <li>Environment variable {@value #ENVVAR_GCP_PROJECT}</li>
 *         <li>ADC default via {@code com.google.cloud.ServiceOptions.getDefaultProjectId()}</li>
 *       </ol>
 *       Dataset defaults to {@value #DEFAULT_DATASET}; table defaults to
 *       {@value #DEFAULT_TABLE}. Both can be overridden via the system properties
 *       {@value #SYSPROP_AUDIT_DATASET} and {@value #SYSPROP_AUDIT_TABLE} (or
 *       environment variables {@value #ENVVAR_AUDIT_DATASET} /
 *       {@value #ENVVAR_AUDIT_TABLE}).
 *   </li>
 *   <li>{@link #BigQueryAuditEventPublisher(BigQuery, String, String, String)} —
 *       explicit constructor for tests and custom-credential wiring.
 *   </li>
 * </ul>
 *
 * <p>Does NOT implement {@link AutoCloseable} — the google-cloud-bigquery 2.x
 * {@link BigQuery} interface is not {@code AutoCloseable}. Consumers manage the
 * client lifecycle.
 *
 * <p>Sprint-14 deliverable for issue #95 (T14.6).
 */
public final class BigQueryAuditEventPublisher implements AuditEventPublisher {

    private static final Logger LOG = LoggerFactory.getLogger(BigQueryAuditEventPublisher.class);

    /** Default dataset when none is configured. */
    public static final String DEFAULT_DATASET = "audit";

    /** Default table when none is configured. */
    public static final String DEFAULT_TABLE = "audit_events";

    /** System property for GCP project override. */
    static final String SYSPROP_GCP_PROJECT = "culvert.gcp.project";

    /** Environment variable for GCP project override. */
    static final String ENVVAR_GCP_PROJECT = "CULVERT_GCP_PROJECT";

    /** System property for audit dataset override. */
    static final String SYSPROP_AUDIT_DATASET = "culvert.audit.dataset";

    /** Environment variable for audit dataset override. */
    static final String ENVVAR_AUDIT_DATASET = "CULVERT_AUDIT_DATASET";

    /** System property for audit table override. */
    static final String SYSPROP_AUDIT_TABLE = "culvert.audit.table";

    /** Environment variable for audit table override. */
    static final String ENVVAR_AUDIT_TABLE = "CULVERT_AUDIT_TABLE";

    /**
     * BigQuery-compatible timestamp format required by
     * {@code QueryParameterValue.timestamp(String)}.
     *
     * <p>The BigQuery SDK (google-cloud-bigquery 2.x) uses the threeten-bp
     * formatter pattern {@code "yyyy-MM-dd HH:mm:ss.SSSSSS"} to validate
     * TIMESTAMP string parameters — it does not accept the ISO-8601 'T'
     * separator. Using a space separator with microsecond precision satisfies
     * the SDK's internal {@code timestampValidator}.
     */
    private static final DateTimeFormatter BQ_TIMESTAMP_FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSSSSS");

    private final BigQuery client;
    private final String projectId;
    private final String fqtn;  // backtick-quoted `project.dataset.table`
    private final AtomicLong auditFailures = new AtomicLong();

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery (T14.6).
     *
     * <p>Resolves the GCP project-id using the three-step precedence chain:
     * sysprop {@value #SYSPROP_GCP_PROJECT} → env {@value #ENVVAR_GCP_PROJECT} → ADC default.
     * Throws {@link IllegalStateException} if none yield a non-blank value.
     *
     * <p>Dataset defaults to {@value #DEFAULT_DATASET}, overridable via
     * sysprop {@value #SYSPROP_AUDIT_DATASET} or env {@value #ENVVAR_AUDIT_DATASET}.
     * Table defaults to {@value #DEFAULT_TABLE}, overridable via
     * sysprop {@value #SYSPROP_AUDIT_TABLE} or env {@value #ENVVAR_AUDIT_TABLE}.
     *
     * <p>Builds the {@link BigQuery} client via
     * {@code BigQueryOptions.getDefaultInstance().getService()} (ADC).
     *
     * @throws IllegalStateException if no GCP project-id is resolvable.
     */
    public BigQueryAuditEventPublisher() {
        this(
            BigQueryOptions.getDefaultInstance().getService(),
            resolveProjectId(),
            resolveStringConfig(SYSPROP_AUDIT_DATASET, ENVVAR_AUDIT_DATASET, DEFAULT_DATASET),
            resolveStringConfig(SYSPROP_AUDIT_TABLE,   ENVVAR_AUDIT_TABLE,   DEFAULT_TABLE)
        );
    }

    /**
     * Explicit constructor for tests and custom-credential wiring.
     *
     * @param client    Pre-built BigQuery client. Required.
     * @param projectId GCP project ID. Required.
     * @param dataset   BigQuery dataset (e.g. {@code "audit"}). Required.
     * @param table     BigQuery table (e.g. {@code "audit_events"}). Required.
     * @throws NullPointerException if any argument is null.
     */
    public BigQueryAuditEventPublisher(BigQuery client, String projectId,
                                       String dataset, String table) {
        this.client    = Objects.requireNonNull(client,    "client must not be null");
        this.projectId = Objects.requireNonNull(projectId, "projectId must not be null");
        Objects.requireNonNull(dataset, "dataset must not be null");
        Objects.requireNonNull(table,   "table must not be null");
        this.fqtn = "`" + projectId + "." + dataset + "." + table + "`";
    }

    /**
     * Writes the audit record as a row in the BigQuery audit table.
     *
     * <p>Uses a parameterised {@code INSERT ... VALUES} DML statement executed
     * via {@code client.query}. Any exception is caught, logged at WARN, and
     * swallowed — audit write failures must never interrupt the pipeline.
     *
     * @param record the audit record to publish; must not be null.
     */
    @Override
    public void publish(AuditRecord record) {
        Objects.requireNonNull(record, "record must not be null");

        String sql = "INSERT INTO " + fqtn + " ("
                + "run_id, pipeline_name, entity_type, source_file, "
                + "record_count, processed_timestamp, processing_duration_seconds, "
                + "success, error_count, audit_hash, metadata_json, published_at"
                + ") VALUES ("
                + "@run_id, @pipeline_name, @entity_type, @source_file, "
                + "@record_count, @processed_timestamp, @processing_duration_seconds, "
                + "@success, @error_count, @audit_hash, @metadata_json, "
                + "CURRENT_TIMESTAMP()"
                + ")";

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(sql)
                .addNamedParameter("run_id",
                        QueryParameterValue.string(record.runId()))
                .addNamedParameter("pipeline_name",
                        QueryParameterValue.string(record.pipelineName()))
                .addNamedParameter("entity_type",
                        QueryParameterValue.string(record.entityType()))
                .addNamedParameter("source_file",
                        QueryParameterValue.string(record.sourceFile()))
                .addNamedParameter("record_count",
                        QueryParameterValue.int64(record.recordCount()))
                .addNamedParameter("processed_timestamp",
                        QueryParameterValue.timestamp(
                                BQ_TIMESTAMP_FMT.format(
                                        record.processedTimestamp().atOffset(ZoneOffset.UTC))))
                .addNamedParameter("processing_duration_seconds",
                        QueryParameterValue.float64(record.processingDurationSeconds()))
                .addNamedParameter("success",
                        QueryParameterValue.bool(record.success()))
                .addNamedParameter("error_count",
                        QueryParameterValue.int64(record.errorCount()))
                .addNamedParameter("audit_hash",
                        QueryParameterValue.string(
                                record.auditHash() == null ? "" : record.auditHash()))
                .addNamedParameter("metadata_json",
                        QueryParameterValue.string(toJsonString(record.metadata())))
                .build();

        try {
            client.query(config);
        } catch (InterruptedException e) {
            // Restore the interrupt flag before swallowing — the caller may check it.
            Thread.currentThread().interrupt();
            auditFailures.incrementAndGet();
            LOG.warn("BigQueryAuditEventPublisher: publish interrupted for runId={}; "
                    + "audit write skipped", record.runId(), e);
        } catch (Exception e) {
            auditFailures.incrementAndGet();
            LOG.warn("BigQueryAuditEventPublisher: failed to publish audit record for "
                    + "runId={} pipeline={}; audit error swallowed",
                    record.runId(), record.pipelineName(), e);
        }
    }

    /**
     * No-op flush — every {@link #publish} call writes immediately and
     * synchronously. Satisfies the contract requirement that flush is
     * idempotent and safe to call on an empty buffer.
     */
    @Override
    public void flush() {
        // Write-through: no buffer to flush.
    }

    /**
     * Returns the cumulative count of audit write failures since this publisher
     * was constructed. Useful in tests and operational alerting.
     */
    public long auditFailureCount() {
        return auditFailures.get();
    }

    /** GCP project ID this publisher writes to. */
    public String projectId() {
        return projectId;
    }

    // --- project-id resolution (mirrors CloudMonitoringMetricsHook.resolveProjectId) ---

    /**
     * Resolves the GCP project-id using the three-step precedence chain.
     *
     * <p>Package-private for testing (allows verification via
     * {@link System#setProperty} without needing to mock static state).
     *
     * @return non-blank project-id string
     * @throws IllegalStateException if all three sources are null or blank
     */
    static String resolveProjectId() {
        // 1. System property (testable via System.setProperty; highest priority)
        String fromProp = System.getProperty(SYSPROP_GCP_PROJECT);
        if (fromProp != null && !fromProp.isBlank()) {
            return fromProp;
        }
        // 2. Environment variable (Dataflow worker / k8s / Cloud Run)
        String fromEnv = System.getenv(ENVVAR_GCP_PROJECT);
        if (fromEnv != null && !fromEnv.isBlank()) {
            return fromEnv;
        }
        // 3. ADC default project (gcloud auth, service account, metadata server)
        String fromAdc = com.google.cloud.ServiceOptions.getDefaultProjectId();
        if (fromAdc != null && !fromAdc.isBlank()) {
            return fromAdc;
        }
        throw new IllegalStateException(
                "Cannot resolve GCP project-id for BigQueryAuditEventPublisher. "
                + "Set one of: system property '" + SYSPROP_GCP_PROJECT + "', "
                + "environment variable '" + ENVVAR_GCP_PROJECT + "', "
                + "or configure Application Default Credentials with a default project "
                + "(gcloud config set project <PROJECT_ID>).");
    }

    /**
     * Resolves a string config value from sysprop → env → default.
     *
     * @param syspropKey system property name
     * @param envKey     environment variable name
     * @param defaultVal fallback when neither sysprop nor env is set
     * @return resolved non-null string
     */
    static String resolveStringConfig(String syspropKey, String envKey, String defaultVal) {
        String fromProp = System.getProperty(syspropKey);
        if (fromProp != null && !fromProp.isBlank()) {
            return fromProp;
        }
        String fromEnv = System.getenv(envKey);
        if (fromEnv != null && !fromEnv.isBlank()) {
            return fromEnv;
        }
        return defaultVal;
    }

    /**
     * Serialise a {@code Map<String, Object>} to a compact JSON string.
     *
     * <p>Uses a simple hand-rolled serialiser to avoid pulling in a JSON
     * library as a compile dependency. Handles String, Number, Boolean, and
     * null values; anything else is converted via {@code toString()}. Nested
     * maps are not supported (the contract's {@link AuditRecord#metadata()}
     * uses shallow string/primitive values in practice).
     */
    static String toJsonString(java.util.Map<String, Object> metadata) {
        if (metadata == null || metadata.isEmpty()) {
            return "{}";
        }
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (java.util.Map.Entry<String, Object> e : metadata.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            // Key — always a string
            sb.append('"').append(escapeJson(e.getKey())).append('"').append(':');
            // Value
            Object v = e.getValue();
            if (v == null) {
                sb.append("null");
            } else if (v instanceof Boolean) {
                sb.append(v);
            } else if (v instanceof Number) {
                sb.append(v);
            } else {
                sb.append('"').append(escapeJson(v.toString())).append('"');
            }
        }
        sb.append('}');
        return sb.toString();
    }

    private static String escapeJson(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
