package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.runners.dataflow.DataflowRunner;
import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Tests for {@link DataflowPipeline}. The validate() logic is exercised
 * with hand-built {@link PipelineStage} stubs; the Beam bridging is
 * verified via the in-process {@link DirectRunner} (no real Dataflow
 * needed).
 */
class DataflowPipelineTest {

    // --- construction ------------------------------------------------------

    @Test
    void rejectsNullName() {
        assertThatThrownBy(() -> new DataflowPipeline(null, List.of(stage("a"))))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void rejectsBlankName() {
        assertThatThrownBy(() -> new DataflowPipeline("   ", List.of(stage("a"))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("blank");
    }

    @Test
    void rejectsEmptyStages() {
        assertThatThrownBy(() -> new DataflowPipeline("p", List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("empty");
    }

    // --- validate ----------------------------------------------------------

    @Test
    void validateAcceptsLinearPipeline() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("read", List.of(), List.of("rows")),
                stage("transform", List.of("rows"), List.of("clean")),
                stage("write", List.of("clean"), List.of())));
        p.validate(); // no throw
        assertThat(p.name()).isEqualTo("p");
        assertThat(p.stages()).hasSize(3);
    }

    @Test
    void validateRejectsDuplicateStageNames() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("read"),
                stage("read")));
        assertThatThrownBy(p::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Duplicate");
    }

    @Test
    void validateRejectsOrphanInput() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("transform", List.of("nonexistent"), List.of("out"))));
        assertThatThrownBy(p::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no producer");
    }

    @Test
    void validateRejectsSelfLoop() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("s", List.of("self-out"), List.of("self-out"))));
        assertThatThrownBy(p::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("own output");
    }

    @Test
    void validateRejectsDuplicateOutput() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("a", List.of(), List.of("shared")),
                stage("b", List.of(), List.of("shared"))));
        assertThatThrownBy(p::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("produced by both");
    }

    @Test
    void validateRejectsCycle() {
        // a -> b -> a (cycle via "x" and "y")
        DataflowPipeline p = new DataflowPipeline("p", List.of(
                stage("a", List.of("y"), List.of("x")),
                stage("b", List.of("x"), List.of("y"))));
        assertThatThrownBy(p::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Cycle");
    }

    // --- buildBeam ---------------------------------------------------------

    @Test
    void buildBeamReturnsNonNullPipelineWithDefaults() {
        DataflowPipeline p = new DataflowPipeline("p", List.of(stage("a")));
        Pipeline beam = p.buildBeam();
        assertThat(beam).isNotNull();
    }

    @Test
    void buildBeamRunsOnDirectRunner() {
        // End-to-end: build a Beam pipeline with DirectRunner options, run
        // it. The pipeline has no transforms yet (sprint-4 scope), but it
        // should still execute cleanly without errors.
        DataflowPipeline p = new DataflowPipeline("p", List.of(stage("a")));
        org.apache.beam.sdk.options.PipelineOptions opts =
                PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);
        Pipeline beam = p.buildBeam(opts);
        // DirectRunner.run() returns immediately for an empty pipeline.
        beam.run().waitUntilFinish();
    }

    // --- runOnDataflow -----------------------------------------------------

    @Test
    void runOnDataflowSetsRunnerOnOptions() {
        // We can't actually submit to Dataflow in a unit test, but we can
        // verify the adapter mutates the options to point at DataflowRunner
        // before passing them down. Build with empty options first (validate
        // happy), then check the runner was set. We do this by capturing
        // the options before .run() would throw on missing project.
        DataflowPipeline p = new DataflowPipeline("p", List.of(stage("a")));
        DataflowPipelineOptions opts = PipelineOptionsFactory.as(DataflowPipelineOptions.class);
        opts.setProject("test-project");
        opts.setRegion("us-central1");
        opts.setTempLocation("gs://test-bucket/temp");
        // We expect runOnDataflow to fail at the actual Dataflow submission
        // step (no creds in test) but only AFTER setting the runner.
        try {
            p.runOnDataflow(opts);
        } catch (Exception expected) {
            // Submission fails — that's fine; the runner should still be set.
        }
        assertThat(opts.getRunner()).isEqualTo(DataflowRunner.class);
    }

    // --- helpers -----------------------------------------------------------

    private static PipelineStage stage(String name) {
        return stage(name, List.of(), List.of());
    }

    private static PipelineStage stage(String name, List<String> inputs, List<String> outputs) {
        return new PipelineStage() {
            @Override
            public String name() {
                return name;
            }

            @Override
            public List<String> inputs() {
                return inputs;
            }

            @Override
            public List<String> outputs() {
                return outputs;
            }

            @Override
            public void execute(RuntimeContext context) {
                // no-op for tests
            }
        };
    }
}
