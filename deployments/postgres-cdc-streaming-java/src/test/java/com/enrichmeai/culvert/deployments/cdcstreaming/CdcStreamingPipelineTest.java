package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * DirectRunner structural test for the two-stage
 * ({@link CdcStreamingStage} → {@link FdpWindowStage}) pipeline, mirroring
 * {@code ReferenceE2EPipelineTest}
 * (deployments/reference-e2e-gcp/src/test/java/com/enrichmeai/culvert/e2e/ReferenceE2EPipelineTest.java).
 *
 * <p>Proves the pipeline validates its topology (odp-rows → fdp-rows edge),
 * builds a Beam pipeline via {@link DataflowPipeline#buildBeam}, and runs to
 * completion on Beam's in-process {@link DirectRunner} — no live GCP, no
 * Docker. This exercises the {@code StageTransform} serialization round-trip
 * (both stages implement {@link java.io.Serializable}) without a live
 * Pub/Sub subscription or BigQuery table, since {@link CdcStreamingStage}
 * and {@link FdpWindowStage} are driven purely through the
 * {@code Source}/{@code Sink}/{@code Warehouse} adapters passed at
 * construction.
 */
class CdcStreamingPipelineTest {

    @Test
    void twoStagePipelineValidatesBuildsAndRunsOnDirectRunner() {
        InMemoryPubSubFakes.QueueSource source = new InMemoryPubSubFakes.QueueSource(List.of());
        InMemoryPubSubFakes.RecordingSink deadLetter = new InMemoryPubSubFakes.RecordingSink();
        InMemoryWarehouse warehouse = new InMemoryWarehouse();

        String odpTable = "project.odp_streaming.customers";
        String fdpTable = "project.fdp_streaming.customers_realtime";

        PipelineStage odpStage = new CdcStreamingStage(source, deadLetter, warehouse, odpTable, "customers");
        PipelineStage fdpStage = new FdpWindowStage(
                warehouse, odpTable, fdpTable, "customers", Duration.ofSeconds(60), true);

        // Declared out of dependency order to exercise DataflowPipeline's topological sort,
        // same pattern as ReferenceE2EPipelineTest.
        DataflowPipeline pipeline = new DataflowPipeline(
                "postgres-cdc-streaming-java-customers", List.of(fdpStage, odpStage));

        // validate() must not throw — DataflowPipeline resolves dependency order
        // from the odp-rows/fdp-rows input/output edges, not declaration order
        // (topologicalOrder() itself is package-private on DataflowPipeline, so
        // it isn't asserted directly here — see ReferenceE2EPipelineTest for the
        // same-package variant of this assertion).
        pipeline.validate();

        RuntimeContext context = DefaultRuntimeContext
                .builder("run-t206-structural", "test")
                .config(Map.of("deployment", "postgres-cdc-streaming-java"))
                .build();

        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);

        Pipeline beam = pipeline.buildBeam(opts, context);
        org.apache.beam.sdk.PipelineResult.State state = beam.run().waitUntilFinish();

        assertThat(state).isEqualTo(org.apache.beam.sdk.PipelineResult.State.DONE);
    }
}
