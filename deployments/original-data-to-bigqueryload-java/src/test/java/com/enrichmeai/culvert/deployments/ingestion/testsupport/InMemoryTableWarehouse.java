package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.LoadOptions;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A {@link Warehouse} double that actually holds rows, so a test can assert
 * what ends up in the table rather than which methods were called.
 *
 * <p>{@link RecordingWarehouse} records calls and returns a canned count — fine
 * for "was a load attempted", useless for "does re-running leave one copy of
 * the data". Answering that needs a double that reads the staged NDJSON back
 * out of the {@link BlobStore} the runner just wrote it to, applies the
 * requested {@link LoadOptions}, and honours the delete the runner issues
 * first. That is what this is.
 *
 * <p><strong>It fails loudly rather than silently skipping.</strong> An
 * {@code execute} call it does not recognise throws. The failure mode for a
 * double like this is the runner changing its DELETE, the pattern no longer
 * matching, the delete quietly not happening, and the idempotency test still
 * passing while the table accumulates duplicates — a green test checking
 * nothing. Better to break the test and be told.
 */
public final class InMemoryTableWarehouse implements Warehouse {

    private static final Gson GSON = new Gson();

    /** {@code DELETE FROM <table> WHERE _extract_date = @extract_date} — the only DML expected. */
    private static final Pattern DELETE_BY_EXTRACT_DATE = Pattern.compile(
            "(?i)^\\s*DELETE\\s+FROM\\s+(\\S+)\\s+WHERE\\s+_extract_date\\s*=\\s*@extract_date\\s*$");

    private final BlobStore blobStore;
    private final Map<String, List<Map<String, Object>>> tables = new LinkedHashMap<>();

    /** Every SQL statement passed to {@link #execute}, in order. */
    public final List<String> executedSql = new ArrayList<>();

    public InMemoryTableWarehouse(BlobStore blobStore) {
        this.blobStore = blobStore;
    }

    /** Current contents of {@code table}. Empty if never written. */
    public List<Map<String, Object>> rowsIn(String table) {
        return tables.getOrDefault(table, List.of());
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema, LoadOptions options) {
        List<Map<String, Object>> staged = readNdjson(uri);

        List<Map<String, Object>> target =
                tables.computeIfAbsent(targetTable, t -> new ArrayList<>());

        switch (options.writeDisposition()) {
            case APPEND -> { /* keep what is there */ }
            case TRUNCATE -> {
                if (options.targetPartition().isPresent()) {
                    throw new UnsupportedOperationException(
                            "This double models unpartitioned tables only; a partition-scoped "
                                    + "TRUNCATE would need partition metadata it does not have.");
                }
                target.clear();
            }
            case ERROR_IF_EXISTS -> {
                if (!target.isEmpty()) {
                    throw new IllegalStateException(
                            "ERROR_IF_EXISTS load into non-empty table " + targetTable);
                }
            }
        }

        target.addAll(staged);
        return staged.size();
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        executedSql.add(sql);

        Matcher delete = DELETE_BY_EXTRACT_DATE.matcher(sql);
        if (delete.matches()) {
            String table = delete.group(1);
            Object extractDate = params.get("extract_date");
            if (extractDate == null) {
                throw new IllegalArgumentException(
                        "DELETE issued without an @extract_date binding: " + sql);
            }
            tables.getOrDefault(table, new ArrayList<>())
                    .removeIf(row -> extractDate.equals(row.get("_extract_date")));
            return;
        }

        // See the class Javadoc: an unrecognised statement means the runner and
        // this double have drifted apart, and pretending to execute it would
        // let an idempotency test pass while the delete never happened.
        throw new UnsupportedOperationException(
                "InMemoryTableWarehouse received SQL it does not model, so it cannot honestly "
                        + "claim to have run it. Teach the double this statement, or check the "
                        + "runner still issues the DELETE it is supposed to. SQL: " + sql);
    }

    private List<Map<String, Object>> readNdjson(String uri) {
        String content = new String(blobStore.get(uri), StandardCharsets.UTF_8);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (String line : content.split("\n")) {
            if (line.isBlank()) {
                continue;
            }
            rows.add(GSON.fromJson(line, new TypeToken<Map<String, Object>>() { }.getType()));
        }
        return rows;
    }

    @Override
    public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
        throw new UnsupportedOperationException("query() is not used by this deployment");
    }

    @Override
    public long merge(String sourceTable, String targetTable, List<String> keys) {
        throw new UnsupportedOperationException("merge() is not used by this deployment");
    }

    @Override
    public long copy(String sourceTable, String targetTable) {
        throw new UnsupportedOperationException("copy() is not used by this deployment");
    }

    @Override
    public boolean tableExists(String fqtn) {
        return tables.containsKey(fqtn);
    }
}
