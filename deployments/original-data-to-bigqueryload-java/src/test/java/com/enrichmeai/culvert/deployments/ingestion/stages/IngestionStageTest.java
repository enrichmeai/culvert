package com.enrichmeai.culvert.deployments.ingestion.stages;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.deployments.ingestion.IngestionPipelines;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.orchestration.DagSpec;
import com.enrichmeai.culvert.orchestration.PipelineToDagSpec;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Structural + DirectRunner tests for the single-stage
 * {@link IngestionPipelines#of} topology, mirroring
 * {@code deployments/reference-e2e-gcp}'s {@code ReferenceE2EPipelineTest}
 * (T12.0, #92) pattern: validate the DAG and confirm it translates to a
 * well-formed {@link DagSpec}.
 *
 * <h2>Why the DirectRunner run below uses a {@link BlobStore}-only stage</h2>
 * <p>{@code DefaultRuntimeContext}'s protocol registry is {@code transient}
 * and is rebuilt worker-side from {@link com.enrichmeai.culvert.autoconfig.AutoConfig#discover()}
 * / {@code ServiceLoader} after Beam (de)serializes the context — including on
 * the in-process {@link DirectRunner}, which still serializes {@code DoFn}s
 * (see {@code DefaultRuntimeContext.java:64-69,101-152} and
 * {@code StageTransform.java:70-93}). Driver-side {@code register(Warehouse.class, ...)}
 * / {@code register(JobControlRepository.class, ...)} calls with in-memory test
 * doubles therefore do NOT reach the worker: only {@link com.enrichmeai.culvert.gcp.gcs.GcsBlobStore}
 * is {@code META-INF/services}-registered with a no-arg (ADC) constructor
 * ({@code data-pipeline-gcp-gcs-java/src/main/resources/META-INF/services/...BlobStore});
 * {@code BigQueryWarehouse}/{@code BigQueryJobControlRepository} require
 * explicit constructor args and are NOT auto-discoverable
 * ({@code BigQueryWarehouse.java:94-99}, deliberately deferred to a future
 * sprint per that class's own TODO). Running the full ingestion flow (which
 * needs {@code Warehouse} + {@code JobControlRepository}) through
 * {@code StageTransform} therefore only works against real GCP-backed
 * adapters today — proven instead by {@link IngestionStageDirectExecuteTest},
 * which calls {@link IngestionStage#execute} directly (no Beam serialization
 * boundary) against the same in-memory test doubles. See the deployment
 * README "Known gaps" section.
 */
class IngestionStageTest {

    private static final String SOURCE_URI = "gs://landing/generic/customers/generic_customers_20260601.csv";
    private static final String TARGET_TABLE = "proj.odp_generic.customers";
    private static final String CSV_HEADER =
            "customer_id,first_name,last_name,ssn,dob,status,created_date";

    @Test
    void pipelineValidates() {
        IngestionStage stage = new IngestionStage(
                "run-structural", "customers", SOURCE_URI, "20260601", TARGET_TABLE,
                "gs://staging/staging", "gs://errors/errors");
        DataflowPipeline pipeline = IngestionPipelines.of(stage);

        pipeline.validate(); // must not throw — single stage, no edges to violate
        assertThat(pipeline.stages()).hasSize(1);
        assertThat(pipeline.stages().get(0).name()).isEqualTo("ingest");
    }

    @Test
    void pipelineTranslatesToWellFormedDagSpec() {
        IngestionStage stage = new IngestionStage(
                "run-dag", "customers", SOURCE_URI, "20260601", TARGET_TABLE,
                "gs://staging/staging", "gs://errors/errors");
        DataflowPipeline pipeline = IngestionPipelines.of(stage);

        DagSpec dag = PipelineToDagSpec.translate(pipeline, "@daily");

        assertThat(dag.dagId()).isEqualTo("original-data-to-bigqueryload");
        assertThat(dag.schedule()).isEqualTo("@daily");
        assertThat(dag.tasks()).hasSize(1);
        assertThat(dag.tasks().get(0).taskId()).isEqualTo("ingest");
        assertThat(dag.edges()).isEmpty();
    }

    /**
     * Proves the Beam wiring itself: {@code buildBeam} + DirectRunner reaches
     * {@link IngestionStage#execute}, without depending on worker-side
     * resolution of {@code Warehouse}/{@code JobControlRepository} (see class
     * Javadoc — those adapters are not {@code ServiceLoader}-discoverable, so
     * a driver-registered in-memory {@code Warehouse}/{@code JobControlRepository}
     * would not reach the worker). This test registers only a {@link BlobStore}
     * (the one adapter that IS {@code ServiceLoader}-discoverable in production,
     * via {@code GcsBlobStore}'s no-arg ADC constructor) and expects
     * {@code execute} to fail fast with the documented
     * {@code IllegalStateException} when it reaches {@code context.get(Warehouse.class)} —
     * proving the pipeline runs on Beam's DirectRunner and really invokes the
     * stage, while being explicit that the full data flow needs real adapters.
     */
    @Test
    void pipelineRunsOnDirectRunnerAndReachesStageExecute() {
        InMemoryBlobStore blobStore = new InMemoryBlobStore();
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260601", CSV_HEADER,
                List.of("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01")));

        IngestionStage stage = new IngestionStage(
                "run-direct-runner", "customers", SOURCE_URI, "20260601", TARGET_TABLE,
                "gs://staging/staging", "gs://errors/errors");
        DataflowPipeline pipeline = IngestionPipelines.of(stage);

        RuntimeContext context = DefaultRuntimeContext.builder("run-direct-runner", "test")
                .register(BlobStore.class, blobStore)
                .config(Map.of("deployment", "original-data-to-bigqueryload-java"))
                .build();

        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);

        Pipeline beam = pipeline.buildBeam(opts, context);

        // DirectRunner executes eagerly inside run() itself (not lazily on
        // waitUntilFinish()). Since the worker-side auto-config fix,
        // BigQueryWarehouse/BigQueryJobControlRepository ARE ServiceLoader-
        // reconstructable on the worker (no-arg ctors via BigQueryDefaults) —
        // execution now proceeds INTO the stage and fails only at the real
        // BigQuery RPC (no live dataset in a unit test). gcp.project pins the
        // client to a fake project so no real ADC project is ever touched.
        // The assertion's spirit is unchanged: the failure must come from
        // *inside* stage.execute() (proving Beam invoked it and the worker
        // rebuilt its adapters), not from construction or adapter resolution.
        System.setProperty("gcp.project", "unit-test-no-such-project");
        System.setProperty("gcp.location", "europe-west2");
        try {
            org.assertj.core.api.Assertions.assertThatThrownBy(beam::run)
                    .as("DirectRunner must reach IngestionStage.execute(); adapters resolve "
                            + "worker-side now, so the failure is the BigQuery RPC itself")
                    .isInstanceOf(org.apache.beam.sdk.Pipeline.PipelineExecutionException.class)
                    .cause()
                    .isInstanceOf(com.google.cloud.bigquery.BigQueryException.class);
        } finally {
            System.clearProperty("gcp.project");
            System.clearProperty("gcp.location");
        }
    }
}
