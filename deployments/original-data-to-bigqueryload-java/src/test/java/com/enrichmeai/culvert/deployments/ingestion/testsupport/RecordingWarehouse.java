package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.function.LongUnaryOperator;

/**
 * Records {@link Warehouse#loadFromUri} calls and returns a caller-controlled
 * row count, so tests can exercise both the reconciled and mismatched paths
 * without a real BigQuery client.
 *
 * <p>Not Mockito-based — this deployment does not depend on Mockito (unlike
 * {@code data-pipeline-tester-java}'s {@code WarehouseFixtures}); a small
 * hand-rolled recorder keeps the test dependency footprint the same as
 * {@code reference-e2e-gcp}'s recording-stub style
 * ({@code deployments/reference-e2e-gcp/src/test/java/.../dq/StubJobControlRepository.java}).
 */
public final class RecordingWarehouse implements Warehouse {

    /** One record per {@link #loadFromUri} call. */
    public record LoadCall(String uri, String targetTable, EntitySchema schema) {
    }

    public final List<LoadCall> loadCalls = new ArrayList<>();

    /** Row count to return from {@link #loadFromUri}. Defaults to the number of NDJSON lines. */
    private LongUnaryOperator rowCountOverride;

    /** Fixes the row count returned by every subsequent {@code loadFromUri} call. */
    public void returnRowCount(long count) {
        this.rowCountOverride = ignoredLineCount -> count;
    }

    @Override
    public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
        return Collections.emptyIterator();
    }

    @Override
    public void execute(String sql, Map<String, Object> params) {
        // no-op
    }

    @Override
    public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
        loadCalls.add(new LoadCall(uri, targetTable, schema));
        return rowCountOverride != null ? rowCountOverride.applyAsLong(0) : 0L;
    }

    @Override
    public long merge(String sourceTable, String targetTable, List<String> keys) {
        throw new UnsupportedOperationException("merge() is not used by this deployment");
    }

    @Override
    public long copy(String sourceTable, String targetTable) {
        return 0L;
    }

    @Override
    public boolean tableExists(String fqtn) {
        return true;
    }
}
