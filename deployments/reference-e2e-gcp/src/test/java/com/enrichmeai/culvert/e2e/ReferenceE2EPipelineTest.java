package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
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
 * DirectRunner structural test for the reference-e2e-gcp skeleton (T12.0, #92).
 *
 * <p>Verifies that the 2-stage pipeline ({@link NoOpReadStage} →
 * {@link NoOpTransformStage}):
 * <ol>
 *   <li>Validates correctly (no cycle, no orphan inputs).</li>
 *   <li>Builds and runs to completion on Beam's in-process
 *       {@link DirectRunner} — no live GCP, no Docker.</li>
 *   <li>Translates to a well-formed {@link DagSpec} via
 *       {@link PipelineToDagSpec}, confirming the scheduler-agnostic
 *       orchestration shape.</li>
 * </ol>
 *
 * <p>Named {@code *Test} (not {@code *IT}) so Maven Surefire picks it up in
 * the default {@code mvn test} phase. Integration tests with a live emulator
 * arrive in S15 (#83) and must be suffixed {@code *IT}.
 *
 * <p>How to run:
 * <pre>
 *   # From deployments/reference-e2e-gcp/:
 *   mvn -o test
 *
 *   # If Culvert artifacts are not yet in ~/.m2, install them first:
 *   cd data-pipeline-libraries-java
 *   mvn -o -pl data-pipeline-core-java,data-pipeline-gcp-dataflow-java,data-pipeline-orchestration-java -am -DskipTests install
 * </pre>
 */
class ReferenceE2EPipelineTest {

    /**
     * The 2-stage pipeline builds, validates, and runs to completion on the
     * DirectRunner. Stages are declared out of dependency order to exercise
     * the topological sort in {@link DataflowPipeline#buildBeam}.
     */
    @Test
    void twoStagePipelineBuildsAndRunsOnDirectRunner() {
        // Declare OUT of dependency order: transform depends on read's output,
        // but is listed first. buildBeam must topologically sort.
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(transform, read));

        RuntimeContext context = DefaultRuntimeContext
                .builder("run-t120-structural", "test")
                .config(Map.of("skeleton", "reference-e2e-gcp"))
                .build();

        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);

        Pipeline beam = pipeline.buildBeam(opts, context);
        // waitUntilFinish() returns DONE when the pipeline completes without error.
        org.apache.beam.sdk.PipelineResult.State state = beam.run().waitUntilFinish();

        assertThat(state).isEqualTo(org.apache.beam.sdk.PipelineResult.State.DONE);
    }

    /**
     * The pipeline topology validates correctly regardless of declaration order.
     *
     * <p>Stages are declared in the wrong order (transform before read);
     * {@link DataflowPipeline#validate()} must not throw because the framework
     * resolves dependency order from input/output edges, not declaration order.
     */
    @Test
    void pipelineValidatesCorrectlyRegardlessOfDeclarationOrder() {
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        // Declared in wrong order intentionally.
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(transform, read));

        // validate() must not throw — the framework resolves order from edges.
        pipeline.validate();
    }

    /**
     * {@link PipelineToDagSpec} translates the 2-stage pipeline to a
     * {@link DagSpec} with the correct task count, edge, and schedule.
     *
     * <p>This confirms the scheduler-agnostic orchestration shape that
     * S12 T12.5 and later sprints will extend.
     */
    @Test
    void pipelineTranslatesToWellFormedDagSpec() {
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(read, transform));

        DagSpec dag = PipelineToDagSpec.translate(pipeline, "@daily");

        assertThat(dag.dagId()).isEqualTo("reference-e2e-gcp");
        assertThat(dag.schedule()).isEqualTo("@daily");
        assertThat(dag.tasks()).hasSize(2);
        assertThat(dag.tasks().get(0).taskId()).isEqualTo("read");
        assertThat(dag.tasks().get(1).taskId()).isEqualTo("transform");
        // One edge: read → transform.
        assertThat(dag.edges()).hasSize(1);
        assertThat(dag.edges().get(0).fromTaskId()).isEqualTo("read");
        assertThat(dag.edges().get(0).toTaskId()).isEqualTo("transform");
    }
}
