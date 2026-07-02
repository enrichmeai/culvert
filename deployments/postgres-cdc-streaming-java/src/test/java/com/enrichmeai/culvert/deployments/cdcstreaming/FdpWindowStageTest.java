package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.enrichmeai.culvert.schema.EntitySchema;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link FdpWindowStage} using {@link InMemoryWarehouse} — no
 * live BigQuery. Mirrors {@code TransformToFDPDoFn} + the
 * {@code WriteToFDP} step of runner.py:299-313, approximated as a
 * wall-clock window (see {@link FdpWindowStage} Javadoc for the documented
 * gap vs. the Python's true watermark-driven Beam windowing).
 */
class FdpWindowStageTest {

    private static final String ODP_TABLE = "project.odp_streaming.customers";
    private static final String FDP_TABLE = "project.fdp_streaming.customers_realtime";

    private RuntimeContext newContext() {
        return DefaultRuntimeContext.builder("run-fdp-1", "test").build();
    }

    @Test
    void rowWithinWindowIsShapedAndWrittenToFdp() {
        InMemoryWarehouse warehouse = new InMemoryWarehouse();
        // Seed an ODP row processed "now" via the stage's own execute() path,
        // so _processed_at is a real, current ISO-8601 timestamp inside the window.
        warehouse.execute(
                "INSERT INTO " + ODP_TABLE + " (customer_id, first_name, last_name, email, ssn, "
                        + "_cdc_operation, _cdc_event_time, _processed_at) VALUES "
                        + "(@p0, @p1, @p2, @p3, @p4, @p5, @p6, @p7)",
                Map.of(
                        "p0", "C001", "p1", "Jane", "p2", "Smith", "p3", "jane@example.com",
                        "p4", "123456789", "p5", "INSERT", "p6", Instant.now().toString(),
                        "p7", Instant.now().toString()));

        FdpWindowStage stage = new FdpWindowStage(
                warehouse, ODP_TABLE, FDP_TABLE, "customers", Duration.ofSeconds(60), true);

        stage.execute(newContext());

        List<Map<String, Object>> fdpRows = warehouse.rowsIn(FDP_TABLE);
        assertThat(fdpRows).hasSize(1);
        Map<String, Object> row = fdpRows.get(0);
        assertThat(row).containsEntry("customer_id", "C001");
        assertThat(row).containsEntry("full_name", "Jane Smith");
        assertThat(row).containsEntry("email_domain", "****");
        assertThat(row).containsEntry("ssn_masked", "XXX-XX-6789");
        assertThat(row).containsEntry("_run_id", "run-fdp-1");
        assertThat(row.get("window_start")).isNotNull();
        assertThat(row.get("window_end")).isNotNull();
    }

    @Test
    void windowPredicateIsIncludedInTheEmittedSql() {
        // InMemoryWarehouse.query() intentionally ignores the WHERE clause
        // (see its class Javadoc) — a real window-exclusion test requires a
        // live BigQuery predicate evaluator, which is out of scope for this
        // in-memory double. What we CAN verify here, without faking a result,
        // is that the stage emits a query containing the window bounds it
        // claims to filter on — i.e. the SQL text itself is correct, even
        // though this fake doesn't enforce it. A BigQueryWarehouseIT-style
        // test (see data-pipeline-gcp-bigquery-java) would be needed to prove
        // the live filtering behaviour.
        RecordingWarehouse recording = new RecordingWarehouse();
        FdpWindowStage stage = new FdpWindowStage(
                recording, ODP_TABLE, FDP_TABLE, "customers", Duration.ofSeconds(60), true);

        stage.execute(newContext());

        assertThat(recording.lastQuerySql).contains("_processed_at >= @windowStart");
        assertThat(recording.lastQuerySql).contains("_processed_at < @windowEnd");
        assertThat(recording.lastQueryParams).containsKeys("windowStart", "windowEnd");
    }

    @Test
    void stageDeclaresExpectedNameAndDependencies() {
        InMemoryWarehouse warehouse = new InMemoryWarehouse();
        FdpWindowStage stage = new FdpWindowStage(
                warehouse, ODP_TABLE, FDP_TABLE, "customers", Duration.ofSeconds(60), true);

        assertThat(stage.name()).isEqualTo("cdc-customers-fdp");
        assertThat(stage.inputs()).containsExactly("odp-rows");
        assertThat(stage.outputs()).containsExactly("fdp-rows");
    }

    /** Captures the last {@code query(sql, params)} call; returns no rows. */
    private static final class RecordingWarehouse implements Warehouse {
        String lastQuerySql;
        Map<String, Object> lastQueryParams;

        @Override
        public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
            this.lastQuerySql = sql;
            this.lastQueryParams = params;
            return Collections.emptyIterator();
        }

        @Override
        public void execute(String sql, Map<String, Object> params) {
            // no-op: no rows are ever queried back, so insertRow is never reached.
        }

        @Override
        public long loadFromUri(String uri, String targetTable, EntitySchema schema) {
            throw new UnsupportedOperationException();
        }

        @Override
        public long merge(String sourceTable, String targetTable, List<String> keys) {
            throw new UnsupportedOperationException();
        }

        @Override
        public long copy(String sourceTable, String targetTable) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean tableExists(String fqtn) {
            return false;
        }
    }
}
