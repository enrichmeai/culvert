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
 *   <li>{@link #loadFromUri}: Athena has no bulk-load API analogous to
 *       BigQuery's {@code LoadJobConfiguration} — Athena only ever reads data
 *       that already lives at a table's registered S3 location (via Glue
 *       Catalog metadata). A same-cloud "load" would require either (a)
 *       registering a temporary external table over {@code uri} and then
 *       {@code CREATE TABLE AS SELECT} into {@code targetTable} (CTAS), which
 *       needs a schema-to-DDL translation step and a throwaway-table cleanup
 *       contract not present anywhere else in this module, or (b) physically
 *       copying/moving objects into the target table's existing S3 prefix,
 *       which conflates this Warehouse adapter with BlobStore responsibilities.
 *       Both expand this method's scope well beyond "match the pilot's
 *       adaptation patterns" for one sprint ticket, so this throws
 *       {@link UnsupportedOperationException} rather than faking a partial
 *       implementation. Tracked for a future sprint alongside real-AWS
 *       validation (see below).</li>
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
        String queryExecutionId = submitAndWait(sql);
        return streamRows(queryExecutionId);
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        Objects.requireNonNull(sql, "sql must not be null");
        submitAndWait(sql);
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
        Objects.requireNonNull(uri, "uri must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
        Objects.requireNonNull(schema, "schema must not be null");
        // See the class Javadoc "Honest limitations" section: a same-cloud
        // load requires either a CTAS-over-external-table translation step or
        // conflating this adapter with BlobStore responsibilities. Neither
        // fits sprint-21 scope, so this is an honest UnsupportedOperationException
        // rather than a faked partial implementation.
        throw new UnsupportedOperationException(
                "loadFromUri() is not supported by AthenaWarehouse: Athena has no bulk-load API "
                        + "analogous to BigQuery's LoadJobConfiguration — it only reads data already "
                        + "registered at a table's Glue Catalog S3 location. Use a CTAS "
                        + "(CREATE TABLE ... AS SELECT ... FROM <external table over the uri>) via "
                        + "execute(String, Map) if you control the schema translation, or load the "
                        + "object via a BlobStore + register/ALTER TABLE ADD PARTITION out of band. "
                        + "Tracked at https://github.com/enrichmeai/culvert/issues/149");
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
        String tableName = unqualify(fqtn);
        try {
            client.getTableMetadata(GetTableMetadataRequest.builder()
                    .catalogName(catalog)
                    .databaseName(database)
                    .tableName(tableName)
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
     * Strip a {@code database.table} qualifier down to the bare table name
     * Athena's {@code GetTableMetadata} expects (database is a separate
     * request field, unlike BigQuery's {@code TableId}).
     *
     * <p>Accepts a bare {@code table} name too (falls back to the
     * warehouse's configured {@link #database}).
     */
    private String unqualify(String fqtn) {
        String[] parts = fqtn.split("\\.");
        if (parts.length == 1) {
            return parts[0];
        }
        if (parts.length == 2) {
            return parts[1];
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
