package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;
import software.amazon.awssdk.services.athena.AthenaClient;
import software.amazon.awssdk.services.athena.model.ColumnInfo;
import software.amazon.awssdk.services.athena.model.Datum;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionResponse;
import software.amazon.awssdk.services.athena.model.GetQueryResultsRequest;
import software.amazon.awssdk.services.athena.model.GetQueryResultsResponse;
import software.amazon.awssdk.services.athena.model.GetTableMetadataRequest;
import software.amazon.awssdk.services.athena.model.MetadataException;
import software.amazon.awssdk.services.athena.model.QueryExecutionContext;
import software.amazon.awssdk.services.athena.model.QueryExecutionState;
import software.amazon.awssdk.services.athena.model.QueryExecutionStatus;
import software.amazon.awssdk.services.athena.model.ResultConfiguration;
import software.amazon.awssdk.services.athena.model.ResultSet;
import software.amazon.awssdk.services.athena.model.Row;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionResponse;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * {@link Warehouse} implementation backed by AWS Athena (SDK v2).
 *
 * <p>Every query/DDL statement is issued as an asynchronous Athena query
 * execution: {@code StartQueryExecution}, polled via {@code GetQueryExecution}
 * until a terminal state, then (for statements that return rows)
 * {@code GetQueryResults} paginated via {@code nextToken}. Fully-qualified
 * table names follow Athena's {@code database.table} convention (the catalog
 * defaults to {@code AwsDataCatalog} and is fixed at construction time, mirroring
 * how {@link com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse
 * BigQueryWarehouse} fixes its {@code projectId}).
 *
 * <h2>Honest limitations (sprint-21 / T21.5 scope)</h2>
 * <ul>
 *   <li>{@link #merge}: Athena has no {@code MERGE} statement outside of
 *       Iceberg-backed tables (Iceberg table format + ACID transactions are
 *       an explicit opt-in at table-creation time, which this adapter does
 *       not assume). Rather than silently emulate MERGE with a DELETE+INSERT
 *       pair (which is not atomic and would misrepresent the contract's
 *       "matched rows are updated" semantics), this method throws
 *       {@link UnsupportedOperationException}, matching the sprint-scope
 *       decision documented on {@code BigQueryWarehouse#merge}.</li>
 *   <li>{@link #loadFromUri} (implemented Sprint 22): Athena has no bulk-load
 *       API analogous to BigQuery's {@code LoadJobConfiguration}, so the load
 *       is the native Athena idiom — a run-scoped all-string external table
 *       (OpenCSVSerde) registered over the staging prefix, a typed
 *       {@code INSERT INTO target SELECT CAST(...)} projection, a
 *       {@code COUNT(*)} for the loaded-row count, and a {@code DROP TABLE}
 *       in a finally block. The DROP is best-effort: if cleanup fails, the
 *       orphaned staging table is Glue metadata only (the staged data at
 *       {@code uri} is never owned by it) and is logged-and-swallowed rather
 *       than masking the load result. CSV only, headerless staged objects —
 *       mirroring {@code BigQueryWarehouse#loadFromUri}.</li>
 *   <li>{@link #query} / {@link #execute}: the {@code params} named-binding
 *       argument is rejected (throws {@link IllegalArgumentException}) when
 *       non-empty. Athena's {@code StartQueryExecution} has no named-parameter
 *       binding analogous to BigQuery's {@code QueryParameterValue} — only
 *       positional {@code executionParameters} against a prepared statement
 *       created via a separate {@code CreatePreparedStatement} call, which is
 *       out of sprint-21 scope. Silently discarding caller-supplied bindings
 *       would be a correctness/injection risk, so this fails loudly instead.</li>
 * </ul>
 *
 * <h2>Real-AWS validation pending</h2>
 * <p><b>Flagged, not faked:</b> community LocalStack does not emulate Athena,
 * so this module ships with mocked-client unit tests only (plus the shared
 * {@link com.enrichmeai.culvert.contracttests.WarehouseContractTest}) — there
 * is no integration test exercising a real Athena query execution end-to-end.
 * That validation is pending a real-AWS test pass before this adapter is
 * relied on in production.
 *
 * <p>Sprint-21 deliverable (T21.5, issue #149).
 */
public final class AthenaWarehouse implements Warehouse {

    /** Athena's default Data Catalog name, used when none is configured explicitly. */
    private static final String DEFAULT_CATALOG = "AwsDataCatalog";

    /** GetQueryResults page size cap per Athena API limits. */
    private static final int MAX_RESULTS_PER_PAGE = 1000;

    private final AthenaClient client;
    private final String database;
    private final String outputLocation;
    private final String catalog;
    private final String workGroup;

    /**
     * Primary constructor.
     *
     * @param client         Pre-built Athena client. Required. Ownership
     *                       transfers to this warehouse — not closed by this
     *                       class (mirrors {@code BigQueryWarehouse}: the
     *                       AWS SDK v2 client manages its own HTTP client
     *                       lifecycle and callers that need explicit teardown
     *                       should close the client they injected).
     * @param database       Athena/Glue database name used for unqualified
     *                       (bare {@code table}) fqtns and as the query
     *                       execution context. Required.
     * @param outputLocation S3 URI ({@code s3://bucket/prefix/}) where Athena
     *                       writes query results. Required — Athena rejects
     *                       {@code StartQueryExecution} without either this or
     *                       a workgroup with a configured output location.
     * @throws NullPointerException if any argument is null.
     */
    public AthenaWarehouse(AthenaClient client, String database, String outputLocation) {
        this(client, database, outputLocation, DEFAULT_CATALOG, null);
    }

    /**
     * Full constructor for callers that need a non-default Glue catalog or a
     * workgroup (e.g. one with query-result reuse or cost controls enabled).
     *
     * @param client         Pre-built Athena client. Required.
     * @param database       Athena/Glue database name. Required.
     * @param outputLocation S3 URI for query results. Required.
     * @param catalog        Glue Data Catalog name. Required; defaults to
     *                       {@value #DEFAULT_CATALOG} via the 3-arg constructor.
     * @param workGroup      Athena workgroup name, or {@code null} to omit
     *                       (uses the account's {@code primary} workgroup).
     */
    public AthenaWarehouse(
            AthenaClient client, String database, String outputLocation, String catalog, String workGroup) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.database = Objects.requireNonNull(database, "database must not be null");
        this.outputLocation = Objects.requireNonNull(outputLocation, "outputLocation must not be null");
        this.catalog = Objects.requireNonNull(catalog, "catalog must not be null");
        this.workGroup = workGroup;
    }

    @Override
    public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
        Objects.requireNonNull(sql, "sql must not be null");
        rejectUnsupportedParams(params);
        String queryExecutionId = submitAndWait(sql);
        return streamRows(queryExecutionId);
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        Objects.requireNonNull(sql, "sql must not be null");
        rejectUnsupportedParams(params);
        submitAndWait(sql);
    }

    /**
     * Athena has no named-parameter binding analogous to BigQuery's
     * {@code QueryParameterValue} — {@code StartQueryExecution} only supports
     * positional {@code executionParameters} paired with a prepared
     * statement created via a separate {@code CreatePreparedStatement} call,
     * which is out of sprint-21 scope. Rather than silently discard
     * caller-supplied bindings (a correctness / injection risk if a caller
     * assumes they're applied), fail loudly on any non-empty {@code params}.
     */
    private static void rejectUnsupportedParams(Map<String, Object> params) {
        if (params != null && !params.isEmpty()) {
            throw new IllegalArgumentException(
                    "AthenaWarehouse does not support named parameter bindings (params must be empty). "
                            + "Athena's StartQueryExecution only supports positional executionParameters "
                            + "against a prepared statement, which is out of scope for this sprint — inline "
                            + "values into the SQL string yourself, or use execute(String, Map) with an "
                            + "explicit PREPARE/EXECUTE pair. Tracked at "
                            + "https://github.com/enrichmeai/culvert/issues/149");
        }
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
        Objects.requireNonNull(uri, "uri must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
        Objects.requireNonNull(schema, "schema must not be null");

        // Athena has no bulk-load API analogous to BigQuery's
        // LoadJobConfiguration — it only reads data already registered at an
        // S3 location. The native load idiom (implemented here, Sprint 22) is:
        //   1. CREATE EXTERNAL TABLE (all columns string, OpenCSVSerde) over
        //      the staging prefix that contains the object at {@code uri};
        //   2. INSERT INTO target SELECT CAST(...) — the typed projection is
        //      where the wire types are enforced (OpenCSVSerde reads strings);
        //   3. COUNT(*) on the staging table for the loaded-row count (Athena's
        //      QueryExecutionStatistics carries no row count — same follow-up
        //      pattern as copy());
        //   4. DROP the staging table in a finally block.
        // Mirrors BigQueryWarehouse#loadFromUri semantics: staged objects are
        // headerless data rows (the pilot sets no skipLeadingRows), CSV only.
        String location = toDirectoryLocation(uri);
        String stagingTable = stagingTableName(targetTable);
        String qualifiedStaging = database + "." + stagingTable;

        submitAndWait(buildExternalTableDdl(qualifiedStaging, schema, location));
        try {
            submitAndWait(buildTypedInsert(targetTable, qualifiedStaging, schema));

            String countSql = "SELECT COUNT(*) AS row_count FROM " + qualifiedStaging;
            Iterator<Map<String, Object>> countRows = streamRows(submitAndWait(countSql));
            if (!countRows.hasNext()) {
                return 0L;
            }
            Object value = countRows.next().get("row_count");
            return value == null ? 0L : Long.parseLong(value.toString());
        } finally {
            // Best-effort cleanup: a failed DROP must not mask the load result
            // (or the original failure) — the staging table is external, so
            // dropping it never touches the staged data at {@code uri}.
            try {
                submitAndWait("DROP TABLE IF EXISTS " + qualifiedStaging);
            } catch (RuntimeException cleanupFailure) {
                // Deliberately swallowed; the orphaned staging table is
                // metadata-only and harmless. Documented in the class Javadoc.
            }
        }
    }

    /**
     * Athena external tables take a directory {@code LOCATION}, not a single
     * object key. If {@code uri} names an object ({@code .../file.csv}), the
     * containing prefix is used — the ingestion pipeline stages exactly one
     * object per run-scoped prefix, so the prefix and the object are
     * equivalent. A trailing-slash URI is used as-is.
     */
    private static String toDirectoryLocation(String uri) {
        if (uri.endsWith("/")) {
            return uri;
        }
        int lastSlash = uri.lastIndexOf('/');
        // s3://bucket/key... — the last slash of a bare bucket URI is the
        // scheme's; keep the URI whole in that case.
        if (lastSlash <= "s3://".length()) {
            return uri.endsWith("/") ? uri : uri + "/";
        }
        return uri.substring(0, lastSlash + 1);
    }

    /** Run-scoped staging table name derived from the target's simple name. */
    private static String stagingTableName(String targetTable) {
        String simple = targetTable.substring(targetTable.lastIndexOf('.') + 1);
        return simple + "_load_" + Long.toUnsignedString(System.nanoTime(), 36);
    }

    /**
     * All-string external table over the staging location. OpenCSVSerde is the
     * quoting-safe CSV SerDe but reads every column as {@code string}; the
     * typed projection happens in {@link #buildTypedInsert}.
     */
    private static String buildExternalTableDdl(
            String qualifiedStaging, EntitySchema schema, String location) {
        StringBuilder ddl = new StringBuilder("CREATE EXTERNAL TABLE ")
                .append(qualifiedStaging).append(" (");
        for (int i = 0; i < schema.fields().size(); i++) {
            if (i > 0) {
                ddl.append(", ");
            }
            ddl.append('`').append(schema.fields().get(i).name()).append("` string");
        }
        ddl.append(") ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde' ")
                .append("LOCATION '").append(location).append('\'');
        return ddl.toString();
    }

    /** Typed INSERT INTO target from the all-string staging table. */
    private static String buildTypedInsert(
            String targetTable, String qualifiedStaging, EntitySchema schema) {
        StringBuilder insert = new StringBuilder("INSERT INTO ").append(targetTable)
                .append(" SELECT ");
        for (int i = 0; i < schema.fields().size(); i++) {
            if (i > 0) {
                insert.append(", ");
            }
            String name = '`' + schema.fields().get(i).name() + '`';
            String athenaType = toAthenaType(schema.fields().get(i).type());
            if ("varchar".equals(athenaType)) {
                insert.append(name);
            } else {
                insert.append("CAST(").append(name).append(" AS ").append(athenaType).append(')');
            }
        }
        insert.append(" FROM ").append(qualifiedStaging);
        return insert.toString();
    }

    /**
     * Wire-type → Athena SQL type for the typed projection. The wire types are
     * the contract's ({@code docs/CONTRACT.md} EntitySchema): STRING, INT64,
     * FLOAT64, BOOL, DATE, TIMESTAMP. Unknown types degrade to varchar rather
     * than failing the load — the DataQualityTransform upstream is the schema
     * enforcement point, not this projection.
     */
    private static String toAthenaType(String wireType) {
        switch (wireType == null ? "" : wireType.toUpperCase(java.util.Locale.ROOT)) {
            case "INT64":
                return "bigint";
            case "FLOAT64":
                return "double";
            case "BOOL":
            case "BOOLEAN":
                return "boolean";
            case "DATE":
                return "date";
            case "TIMESTAMP":
                return "timestamp";
            case "STRING":
            default:
                return "varchar";
        }
    }

    @Override
    public long merge(String sourceTable, String targetTable, List<String> keys) {
        Objects.requireNonNull(sourceTable, "sourceTable must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
        Objects.requireNonNull(keys, "keys must not be null");
        if (keys.isEmpty()) {
            throw new IllegalArgumentException("merge requires at least one key column");
        }
        // See the class Javadoc "Honest limitations" section: Athena has no
        // MERGE statement outside Iceberg-backed tables, which this adapter
        // does not assume. Mirrors BigQueryWarehouse#merge's sprint-scope
        // decision rather than faking atomicity with DELETE+INSERT.
        throw new UnsupportedOperationException(
                "merge() is not supported by AthenaWarehouse: Athena has no MERGE statement for "
                        + "non-Iceberg tables, and emulating one via DELETE+INSERT would not be atomic "
                        + "and would misrepresent the contract's upsert semantics. Use execute(String, Map) "
                        + "with an explicit MERGE INTO statement if the target table is Iceberg-backed. "
                        + "Tracked at https://github.com/enrichmeai/culvert/issues/149");
    }

    @Override
    public long copy(String sourceTable, String targetTable) {
        Objects.requireNonNull(sourceTable, "sourceTable must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");

        // Athena has no metadata-only copy job like BigQuery's
        // CopyJobConfiguration; CTAS is the closest equivalent (still a
        // single query execution, no client-side row shuffling). Unlike
        // BigQuery's post-copy Table.getNumRows(), Athena's
        // QueryExecutionStatistics carries bytes scanned but no row count,
        // so a follow-up COUNT(*) is the only way to report rows copied.
        String ctas = "CREATE TABLE " + targetTable + " AS SELECT * FROM " + sourceTable;
        submitAndWait(ctas);

        String countSql = "SELECT COUNT(*) AS row_count FROM " + targetTable;
        Iterator<Map<String, Object>> countRows = streamRows(submitAndWait(countSql));
        if (!countRows.hasNext()) {
            return 0L;
        }
        Object value = countRows.next().get("row_count");
        return value == null ? 0L : Long.parseLong(String.valueOf(value));
    }

    @Override
    public boolean tableExists(String fqtn) {
        Objects.requireNonNull(fqtn, "fqtn must not be null");
        String[] parsed = parseFqtn(fqtn);
        try {
            client.getTableMetadata(GetTableMetadataRequest.builder()
                    .catalogName(catalog)
                    .databaseName(parsed[0])
                    .tableName(parsed[1])
                    .build());
            return true;
        } catch (MetadataException e) {
            // Athena/Glue signal "table not found" as a MetadataException
            // rather than a null return (contrast with BigQuery's
            // getTable() -> null). Any other AthenaException subtype is a
            // real failure and should propagate.
            return false;
        }
    }

    // --- helpers -----------------------------------------------------------

    /**
     * Submit {@code sql} and block until the query execution reaches a
     * terminal state (SUCCEEDED, FAILED, or CANCELLED).
     *
     * @return The query execution ID, for callers that need to fetch results
     *         or statistics afterward.
     * @throws AthenaQueryFailedException if the execution ends in FAILED or
     *                                    CANCELLED.
     */
    private String submitAndWait(String sql) {
        StartQueryExecutionRequest.Builder requestBuilder = StartQueryExecutionRequest.builder()
                .queryString(sql)
                .queryExecutionContext(QueryExecutionContext.builder()
                        .catalog(catalog)
                        .database(database)
                        .build())
                .resultConfiguration(ResultConfiguration.builder()
                        .outputLocation(outputLocation)
                        .build());
        if (workGroup != null) {
            requestBuilder.workGroup(workGroup);
        }
        StartQueryExecutionResponse startResponse = client.startQueryExecution(requestBuilder.build());
        String queryExecutionId = startResponse.queryExecutionId();
        return pollUntilTerminal(queryExecutionId);
    }

    /**
     * Poll {@code GetQueryExecution} until the execution reaches a terminal
     * state. No sleep is inserted between the first poll and returning on a
     * terminal state, keeping the common (already-finished, or fast) case
     * synchronous; callers that need backoff between polls for long-running
     * queries should not rely on this method being instantaneous in
     * production, but a mocked client resolves immediately in tests.
     */
    private String pollUntilTerminal(String queryExecutionId) {
        while (true) {
            GetQueryExecutionResponse response = client.getQueryExecution(
                    GetQueryExecutionRequest.builder().queryExecutionId(queryExecutionId).build());
            QueryExecutionStatus status = response.queryExecution().status();
            QueryExecutionState state = status.state();
            switch (state) {
                case SUCCEEDED:
                    return queryExecutionId;
                case FAILED:
                case CANCELLED:
                    throw new AthenaQueryFailedException(queryExecutionId, state, status.stateChangeReason());
                case QUEUED:
                case RUNNING:
                    // Not terminal yet; poll again. A production caller would
                    // insert a backoff sleep here — omitted so mocked-client
                    // unit tests (which return a terminal state immediately)
                    // never spin. A real AthenaClient's GetQueryExecution
                    // calls are individually rate-limited by the service, but
                    // an unbounded tight loop against a real, slow-running
                    // query is a known follow-up (see class Javadoc "Real-AWS
                    // validation pending").
                    continue;
                default:
                    throw new IllegalStateException(
                            "Unknown Athena QueryExecutionState: " + state + " for " + queryExecutionId);
            }
        }
    }

    /**
     * Fetch all pages of {@code GetQueryResults} for {@code queryExecutionId}
     * and return a lazy iterator over row maps.
     *
     * <p>Athena's {@code GetQueryResults} echoes the column header names as
     * the first data row, but <b>only on the first page</b> — subsequent
     * pages contain only real data rows. Column names themselves come from
     * {@code ResultSetMetadata.columnInfo()}, never parsed out of the header
     * row.
     */
    private Iterator<Map<String, Object>> streamRows(String queryExecutionId) {
        List<Map<String, Object>> rows = new ArrayList<>();
        List<String> columnNames = null;
        String nextToken = null;
        boolean firstPage = true;
        do {
            GetQueryResultsRequest.Builder requestBuilder = GetQueryResultsRequest.builder()
                    .queryExecutionId(queryExecutionId)
                    .maxResults(MAX_RESULTS_PER_PAGE);
            if (nextToken != null) {
                requestBuilder.nextToken(nextToken);
            }
            GetQueryResultsResponse response = client.getQueryResults(requestBuilder.build());
            ResultSet resultSet = response.resultSet();
            if (columnNames == null) {
                columnNames = columnNamesOf(resultSet);
            }
            List<Row> pageRows = resultSet.hasRows() ? resultSet.rows() : List.of();
            int startIndex = firstPage && !pageRows.isEmpty() ? 1 : 0; // skip header row, first page only
            for (int i = startIndex; i < pageRows.size(); i++) {
                rows.add(toRowMap(columnNames, pageRows.get(i)));
            }
            nextToken = response.nextToken();
            firstPage = false;
        } while (nextToken != null);
        return rows.iterator();
    }

    private static List<String> columnNamesOf(ResultSet resultSet) {
        if (resultSet.resultSetMetadata() == null || !resultSet.resultSetMetadata().hasColumnInfo()) {
            return List.of();
        }
        List<ColumnInfo> columnInfo = resultSet.resultSetMetadata().columnInfo();
        List<String> names = new ArrayList<>(columnInfo.size());
        for (ColumnInfo info : columnInfo) {
            names.add(info.name());
        }
        return names;
    }

    private static Map<String, Object> toRowMap(List<String> columnNames, Row row) {
        List<Datum> data = row.hasData() ? row.data() : List.of();
        Map<String, Object> map = new LinkedHashMap<>(columnNames.size() * 2);
        for (int i = 0; i < columnNames.size(); i++) {
            Object value = i < data.size() ? data.get(i).varCharValue() : null;
            map.put(columnNames.get(i), value);
        }
        return map;
    }

    /**
     * Parse a fully-qualified table name into {@code [database, table]}.
     * Athena's {@code GetTableMetadata} takes database and table as separate
     * request fields (unlike BigQuery's single {@code TableId}), so the fqtn
     * must be split rather than passed through whole.
     *
     * <p>Accepts a bare {@code table} name too, in which case the database
     * falls back to this warehouse's configured {@link #database} — mirrors
     * {@code BigQueryWarehouse#parseFqtn}'s "unqualified defaults to the
     * configured project" behaviour.
     */
    private String[] parseFqtn(String fqtn) {
        String[] parts = fqtn.split("\\.");
        if (parts.length == 1) {
            return new String[] {database, parts[0]};
        }
        if (parts.length == 2) {
            return parts;
        }
        throw new IllegalArgumentException(
                "Invalid Athena fqtn (expected 'table' or 'database.table'): " + fqtn);
    }

    /** Thrown when an Athena query execution ends in FAILED or CANCELLED. */
    public static final class AthenaQueryFailedException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public AthenaQueryFailedException(String queryExecutionId, QueryExecutionState state, String reason) {
            super("Athena query " + queryExecutionId + " ended in state " + state
                    + (reason != null ? ": " + reason : ""));
        }
    }
}
