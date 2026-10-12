package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.deployments.ingestion.stages.IngestionStage;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.WorkerDoubles;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.enrichmeai.culvert.schema.SchemaField;
import com.enrichmeai.culvert.schema.SchemaFileException;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The loader on Beam's DirectRunner with {@code --schemaUri}: a new entity, which the loader has
 * no code for, loads, quarantines and reconciles; and a built-in entity given as a schema file
 * runs exactly as the built-in does.
 *
 * <p>The run goes through the real Beam path (stage serialized, adapters rebuilt on the worker):
 * {@link WorkerDoubles} gives the worker in-memory adapters. The stage is built the way
 * {@link IngestionMain} builds it, from {@link IngestionMain#entityArgs}.
 */
class SchemaFileDirectRunnerTest {

    private static final String ORDERS_SCHEMA = """
            entity: orders
            headers: [order_id, customer_id, quantity, amount, ordered_on]
            fields:
              - {name: order_id, type: STRING, required: true}
              - {name: customer_id, type: STRING, required: true}
              - {name: quantity, type: STRING, required: true}
              - {name: amount, type: STRING}
              - {name: ordered_on, type: DATE}
            envelope:
              system_id: Retail
            """;
    private static final String ORDERS_HEADER = "order_id,customer_id,quantity,amount,ordered_on";
    private static final String CUSTOMERS_HEADER = "customer_id,first_name,last_name,ssn,dob,status,created_date";

    private InMemoryBlobStore blobStore;
    private RecordingWarehouse warehouse;
    private RecordingJobControlRepository jobControl;

    @BeforeEach
    void installWorkerDoubles() {
        blobStore = new InMemoryBlobStore();
        warehouse = new RecordingWarehouse();
        jobControl = new RecordingJobControlRepository();
        WorkerDoubles.install(blobStore, warehouse, jobControl);
    }

    @AfterEach
    void uninstallWorkerDoubles() {
        WorkerDoubles.uninstall();
    }

    @Test
    void aNewEntityLoadsQuarantinesAndReconciles(@TempDir Path dir) throws Exception {
        Path schema = dir.resolve("orders.schema.yaml");
        Files.writeString(schema, ORDERS_SCHEMA);
        String source = "gs://landing/retail/orders/retail_orders_20260601.csv";
        blobStore.seed(source, EnvelopeFixtures.buildFileBytes("Retail", "orders", "20260601", ORDERS_HEADER, List.of(
                "ord-1,cust-1,2,19.99,2026-06-01",
                "ord-2,cust-2,1,5.00,2026-06-01",
                "ord-3,cust-3,1",                              // too few columns
                "ord-4,cust-4,3,2.50,2026-06-01,extra")));     // too many
        warehouse.returnRowCount(2);

        // The launcher's resolution: a local path, and no --entity, so the file names the run.
        IngestionMain.EntityArgs args = IngestionMain.entityArgs(Map.of("schemaUri", schema.toString()), blobStore);
        assertThat(args.entity()).isEqualTo("orders");
        runOnDirectRunner("run-orders", args, schema.toString(), source, "proj.odp_retail.orders");

        // Loaded: the two valid rows, against the file's schema plus the audit columns.
        assertThat(warehouse.loadCalls).hasSize(1);
        assertThat(warehouse.loadCalls.get(0).schema().fields()).extracting(SchemaField::name).containsExactly(
                "order_id", "customer_id", "quantity", "amount", "ordered_on",
                "_run_id", "_extract_date", "_processed_at");
        assertThat(stagedRows(warehouse.loadCalls.get(0).uri())).extracting(r -> r.get("order_id").getAsString())
                .containsExactly("ord-1", "ord-2");
        // Quarantined: the other two.
        assertThat(quarantinedLines()).hasSize(2);
        // Reconciled and recorded: 4 declared = 2 loaded + 2 quarantined, the job SUCCEEDED, under
        // the system id the file's envelope names.
        assertThat(jobControl.statusUpdates).extracting(RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING, JobStatus.SUCCEEDED);
        assertThat(jobControl.statusUpdates.get(1).totalRecords()).contains(2L);
        // The quarantine handler notes the quarantined rows on the job, as for a built-in entity.
        assertThat(jobControl.markFailedCalls).extracting(RecordingJobControlRepository.MarkFailedCall::errorCode)
                .containsExactly("DQ_VALIDATION_FAILURE");
        PipelineJob job = jobControl.job("run-orders").orElseThrow();
        assertThat(job.systemId()).isEqualTo("Retail");
        assertThat(job.entityType()).contains("orders");
    }

    @Test
    void aBuiltInEntityRunsTheSameFromItsSchemaFile() {
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                "cust-2,Alan,Turing,987-65-4321");                       // too few columns
        String source = "gs://landing/generic/customers/generic_customers_20260601.csv";
        blobStore.seed(source, EnvelopeFixtures.buildFileBytes("Generic", "customers", "20260601", CUSTOMERS_HEADER, rows));
        warehouse.returnRowCount(1);

        runOnDirectRunner("run-built-in", IngestionMain.entityArgs(Map.of("entity", "customers"), blobStore),
                null, source, "proj.odp_generic.customers");
        String schemaFile = Path.of("schemas", "customers.schema.yaml").toString();
        runOnDirectRunner("run-from-file", IngestionMain.entityArgs(Map.of("schemaUri", schemaFile), blobStore),
                schemaFile, source, "proj.odp_generic.customers");

        assertThat(warehouse.loadCalls).hasSize(2);
        assertThat(warehouse.loadCalls.get(1).schema()).isEqualTo(warehouse.loadCalls.get(0).schema());
        assertThat(withoutRunColumns(stagedRows(warehouse.loadCalls.get(1).uri())))
                .isEqualTo(withoutRunColumns(stagedRows(warehouse.loadCalls.get(0).uri())));
        assertThat(quarantinedLines()).hasSize(2);   // one per run
        assertThat(jobControl.statusUpdates).extracting(RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING, JobStatus.SUCCEEDED, JobStatus.RUNNING, JobStatus.SUCCEEDED);
        PipelineJob builtIn = jobControl.job("run-built-in").orElseThrow();
        PipelineJob fromFile = jobControl.job("run-from-file").orElseThrow();
        assertThat(fromFile.systemId()).isEqualTo(builtIn.systemId());
        assertThat(fromFile.pipelineName()).isEqualTo(builtIn.pipelineName());
        assertThat(jobControl.markFailedCalls).extracting(RecordingJobControlRepository.MarkFailedCall::errorCode)
                .containsExactly("DQ_VALIDATION_FAILURE", "DQ_VALIDATION_FAILURE");
    }

    @Test
    void anExplicitEntityIsTheRunsLabel(@TempDir Path dir) throws Exception {
        Path schema = dir.resolve("orders.schema.yaml");
        Files.writeString(schema, ORDERS_SCHEMA);

        assertThat(IngestionMain.entityArgs(Map.of("schemaUri", schema.toString(), "entity", "orders_eu"), blobStore))
                .isEqualTo(new IngestionMain.EntityArgs("orders_eu", ORDERS_SCHEMA));
    }

    @Test
    void aBadSchemaFileStopsTheLaunchBeforeAnythingRuns(@TempDir Path dir) throws Exception {
        Path schema = dir.resolve("orders.schema.yaml");
        Files.writeString(schema, ORDERS_SCHEMA.replace("{name: quantity, type: STRING", "{name: quantity, type: INTEGER"));

        assertThatThrownBy(() -> IngestionMain.entityArgs(Map.of("schemaUri", schema.toString()), blobStore))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageContaining("fields[2].type: unknown type 'INTEGER'");
        assertThat(jobControl.statusUpdates).isEmpty();
    }

    @Test
    void aFieldNamedLikeAnAuditColumnIsRefused(@TempDir Path dir) throws Exception {
        Path schema = dir.resolve("orders.schema.yaml");
        Files.writeString(schema, ORDERS_SCHEMA
                .replace("[order_id, customer_id,", "[order_id, _run_id, customer_id,")
                .replace("  - {name: customer_id,", "  - {name: _run_id, type: STRING}\n  - {name: customer_id,"));

        assertThatThrownBy(() -> IngestionMain.entityArgs(Map.of("schemaUri", schema.toString()), blobStore))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageContaining("field '_run_id' is an audit column this loader adds to every row");
    }

    @Test
    void withoutASchemaFileAnUnknownEntityIsRefused() {
        IngestionRunner runner = new IngestionRunner(blobStore, warehouse, jobControl, "gs://s/staging", "gs://e/errors");

        assertThatThrownBy(() -> runner.run(new IngestionRequest("run-x", "orders", "gs://l/x.csv", "20260601", "p.d.t")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Unknown entity: orders")
                .hasMessageContaining("--schemaUri");
    }

    // ------------------------------------------------------------------ helpers

    private void runOnDirectRunner(String runId, IngestionMain.EntityArgs args, String schemaUri,
                                   String source, String targetTable) {
        IngestionStage stage = new IngestionStage(runId, args.entity(), source, "20260601", targetTable,
                "gs://staging/staging", "gs://errors/errors", schemaUri, args.schemaText());
        RuntimeContext context = DefaultRuntimeContext.builder(runId, "test").build();
        PipelineOptions options = PipelineOptionsFactory.create();
        options.setRunner(DirectRunner.class);
        IngestionPipelines.of(stage).buildBeam(options, context).run().waitUntilFinish();
    }

    private List<JsonObject> stagedRows(String uri) {
        List<JsonObject> rows = new ArrayList<>();
        for (String line : new String(blobStore.getOrNull(uri), StandardCharsets.UTF_8).split("\n")) {
            if (!line.isBlank()) {
                rows.add(JsonParser.parseString(line).getAsJsonObject());
            }
        }
        return rows;
    }

    private static List<JsonObject> withoutRunColumns(List<JsonObject> rows) {
        rows.forEach(r -> {
            r.remove("_run_id");
            r.remove("_processed_at");
        });
        return rows;
    }

    private List<String> quarantinedLines() {
        List<String> lines = new ArrayList<>();
        for (String uri : blobStore.writtenUris()) {
            if (uri.startsWith("gs://errors/")) {
                for (String line : new String(blobStore.getOrNull(uri), StandardCharsets.UTF_8).split("\n")) {
                    if (!line.isBlank()) {
                        lines.add(line);
                    }
                }
            }
        }
        return lines;
    }
}
