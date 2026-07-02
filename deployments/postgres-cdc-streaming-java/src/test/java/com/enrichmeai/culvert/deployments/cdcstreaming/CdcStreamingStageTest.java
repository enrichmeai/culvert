package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link CdcStreamingStage} using in-memory adapters
 * ({@link InMemoryWarehouse}, {@link InMemoryPubSubFakes}) — no live GCP.
 *
 * <p>Exercises the read → parse → ODP-write → dead-letter flow end to end,
 * mirroring runner.py's {@code ReadFromPubSub → ParseCDCEvent → FilterValid
 * → TransformToODP → AddAuditColumns → WriteToODP} chain
 * (gcp-pipeline-reference deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/runner.py:249-283).
 */
class CdcStreamingStageTest {

    private static final String ODP_TABLE = "project.odp_streaming.customers";

    private static final String INSERT_EVENT = """
            {
              "before": null,
              "after": {"customer_id": "C001", "full_name": "Jane Smith", "email": "jane@example.com"},
              "source": {"connector": "postgresql", "table": "customers", "db": "customers_db", "schema": "public", "ts_ms": 1709807400000},
              "op": "c",
              "ts_ms": 1709807400123
            }
            """;

    private RuntimeContext newContext() {
        return DefaultRuntimeContext.builder("run-test-1", "test").build();
    }

    @Test
    void validEventIsWrittenToOdpWithAuditColumns() {
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(List.of(INSERT_EVENT));
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        CdcStreamingStage stage = new CdcStreamingStage(source, deadLetter, warehouse, ODP_TABLE, "customers");
        RuntimeContext context = newContext();

        stage.execute(context);

        List<Map<String, Object>> odpRows = warehouse.rowsIn(ODP_TABLE);
        assertThat(odpRows).hasSize(1);
        Map<String, Object> row = odpRows.get(0);
        assertThat(row).containsEntry("customer_id", "C001");
        assertThat(row).containsEntry("_cdc_operation", "INSERT");
        assertThat(row).containsEntry("_run_id", "run-test-1");
        assertThat(row.get("_processed_at")).isNotNull();
        // ODP shaping strips nulls — nothing null-valued should have survived.
        assertThat(row.values()).doesNotContainNull();
        assertThat(deadLetter.written).isEmpty();
    }

    @Test
    void malformedEventIsRoutedToDeadLetterNotOdp() {
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(
                List.of("not valid json {{{"));
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        CdcStreamingStage stage = new CdcStreamingStage(source, deadLetter, warehouse, ODP_TABLE, "customers");

        stage.execute(newContext());

        assertThat(warehouse.rowsIn(ODP_TABLE)).isEmpty();
        assertThat(deadLetter.writtenPayloads()).containsExactly("not valid json {{{");
    }

    @Test
    void mixedBatchSplitsBetweenOdpAndDeadLetter() {
        String schemaChangeEvent = "{\"op\": \"m\", \"source\": {\"table\": \"customers\"}}";
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(
                List.of(INSERT_EVENT, schemaChangeEvent));
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        CdcStreamingStage stage = new CdcStreamingStage(source, deadLetter, warehouse, ODP_TABLE, "customers");

        stage.execute(newContext());

        assertThat(warehouse.rowsIn(ODP_TABLE)).hasSize(1);
        assertThat(deadLetter.written).hasSize(1);
    }

    @Test
    void emptyBatchWritesNothingAndDeadLettersNothing() {
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(List.of());
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        CdcStreamingStage stage = new CdcStreamingStage(source, deadLetter, warehouse, ODP_TABLE, "customers");

        stage.execute(newContext());

        assertThat(warehouse.rowsIn(ODP_TABLE)).isEmpty();
        assertThat(deadLetter.written).isEmpty();
    }

    @Test
    void stageDeclaresExpectedNameAndOutputs() {
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(List.of());
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        CdcStreamingStage stage = new CdcStreamingStage(source, deadLetter, warehouse, ODP_TABLE, "customers");

        assertThat(stage.name()).isEqualTo("cdc-customers-odp");
        assertThat(stage.inputs()).isEmpty();
        assertThat(stage.outputs()).containsExactly("odp-rows");
    }
}
