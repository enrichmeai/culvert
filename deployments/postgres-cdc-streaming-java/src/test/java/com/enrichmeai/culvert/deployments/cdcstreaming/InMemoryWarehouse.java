package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * In-memory {@link Warehouse} test double, mirroring the
 * {@code InMemoryBlobStore}/{@code StubJobControlRepository} pattern used by
 * {@code reference-e2e-gcp}'s DQ slice tests
 * (deployments/reference-e2e-gcp/src/test/java/com/enrichmeai/culvert/e2e/dq/InMemoryBlobStore.java).
 *
 * <p>Supports exactly the two operations {@link CdcStreamingStage} and
 * {@link FdpWindowStage} issue:
 * <ul>
 *   <li>{@link #execute(String, Map)} — parses the deployment's own
 *       {@code INSERT INTO <table> (col, ...) VALUES (@p0, ...)} shape
 *       (see {@code CdcStreamingStage#writeToOdp} /
 *       {@code FdpWindowStage#insertRow}) and appends a row to the named
 *       table's in-memory list.</li>
 *   <li>{@link #query(String, Map)} — returns all rows appended to the
 *       table named in a {@code SELECT * FROM <table> WHERE ...} statement,
 *       ignoring the WHERE clause (tests control the row set precisely, so
 *       a full predicate evaluator is unnecessary here).</li>
 * </ul>
 *
 * <p>Not a general-purpose SQL engine — it is intentionally narrow to the
 * two query shapes this deployment emits, exactly as
 * {@code StubJobControlRepository} narrows itself to the methods its
 * caller invokes.
 */
final class InMemoryWarehouse implements Warehouse, java.io.Serializable {

    private static final Pattern INSERT_PATTERN = Pattern.compile(
            "(?is)INSERT INTO\\s+(\\S+)\\s*\\(([^)]*)\\)\\s*VALUES\\s*\\(([^)]*)\\)");
    private static final Pattern SELECT_TABLE_PATTERN = Pattern.compile(
            "(?is)FROM\\s+(\\S+)");

    private final Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();

    List<Map<String, Object>> rowsIn(String table) {
        return tables.getOrDefault(table, List.of());
    }

    @Override
    public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
        Matcher matcher = SELECT_TABLE_PATTERN.matcher(sql);
        if (!matcher.find()) {
            throw new IllegalArgumentException("InMemoryWarehouse cannot parse query: " + sql);
        }
        String table = matcher.group(1).trim();
        return new ArrayList<>(tables.getOrDefault(table, Collections.emptyList())).iterator();
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        Matcher matcher = INSERT_PATTERN.matcher(sql);
        if (!matcher.find()) {
            throw new IllegalArgumentException("InMemoryWarehouse only supports INSERT statements in tests: " + sql);
        }
        String table = matcher.group(1).trim();
        String[] columns = matcher.group(2).split(",");
        String[] placeholders = matcher.group(3).split(",");

        Map<String, Object> row = new LinkedHashMap<>();
        for (int i = 0; i < columns.length; i++) {
            String column = columns[i].trim();
            String placeholder = placeholders[i].trim().substring(1); // strip leading '@'
            row.put(column, params.get(placeholder));
        }
        tables.computeIfAbsent(table, t -> new ArrayList<>()).add(row);
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
        throw new UnsupportedOperationException("not used by this deployment's tests");
    }

    @Override
    public long merge(String sourceTable, String targetTable, List<String> keys) {
        throw new UnsupportedOperationException("not used by this deployment's tests");
    }

    @Override
    public long copy(String sourceTable, String targetTable) {
        throw new UnsupportedOperationException("not used by this deployment's tests");
    }

    @Override
    public boolean tableExists(String fqtn) {
        return tables.containsKey(fqtn);
    }
}
