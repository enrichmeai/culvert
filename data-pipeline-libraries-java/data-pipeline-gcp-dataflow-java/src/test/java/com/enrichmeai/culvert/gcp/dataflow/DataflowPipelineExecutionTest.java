package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.Serializable;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Sprint-9 T9.4 (scope-capped): prove that a {@link DataflowPipeline} built
 * from <strong>stub</strong> {@link PipelineStage} impls executes its topology
 * on Beam's {@link DirectRunner}.
 *
 * <p>No real BigQuery/GCS/Pub-Sub adapters are wired here — real-adapter
 * wiring + real-fixture ITs are deferred to Sprint-10 T10.0, once the
 * IT-support module supplies fixtures. The stubs only record that they ran.
 *
 * <p>The test verifies two things, split because of the transform's design:
 *
 * <ul>
 *   <li><strong>Execution:</strong> both stages run to completion on the
 *       DirectRunner, surviving a real serialization round-trip of the stage
 *       + {@link RuntimeContext} into the DoFn. Stages are deliberately
 *       <em>declared out of dependency order</em> to exercise the topological
 *       wiring in {@code buildBeam}.</li>
 *   <li><strong>Dependency order:</strong> asserted separately and
 *       deterministically via {@link DataflowPipeline#topologicalOrder()}.
 *       Temporal ordering between the independent {@code PBegin}-rooted stage
 *       transforms is a runner scheduling concern (Sprint-9 stages don't pass
 *       elements between each other); element-level ordering is sprint-future.</li>
 * </ul>
 */
class DataflowPipelineExecutionTest {

    /**
     * Static recorder keyed by stage name. Static (not an instance field) so
     * it is reachable from the worker-side DoFn without being captured into
     * the serialized graph. On the in-process DirectRunner the worker shares
     * this JVM, so the markers are observable after {@code waitUntilFinish()}.
     */
    static final ConcurrentHashMap<String, Boolean> EXECUTED = new ConcurrentHashMap<>();

    @BeforeEach
    void resetRecorder() {
        EXECUTED.clear();
    }

    @Test
    void twoStagePipelineExecutesOnDirectRunner() {
        // Declare OUT of dependency order: "transform" depends on "read"'s
        // output, but is declared first. buildBeam must topologically sort.
        PipelineStage read = new RecordingStage("read", List.of(), List.of("rows"));
        PipelineStage transform = new RecordingStage("transform", List.of("rows"), List.of("clean"));
        DataflowPipeline pipeline = new DataflowPipeline("two-stage", List.of(transform, read));

        RuntimeContext context = DefaultRuntimeContext
                .builder("run-t94", "test")
                .config(Map.of("dataset", "events"))
                .build();

        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);

        Pipeline beam = pipeline.buildBeam(opts, context);
        beam.run().waitUntilFinish();

        assertThat(EXECUTED).containsKeys("read", "transform");
        assertThat(EXECUTED.get("read")).isTrue();
        assertThat(EXECUTED.get("transform")).isTrue();
    }

    @Test
    void buildBeamComputesDependencyOrderRegardlessOfDeclaration() {
        // a -> b -> c, declared as [c, a, b].
        PipelineStage a = new RecordingStage("a", List.of(), List.of("x"));
        PipelineStage b = new RecordingStage("b", List.of("x"), List.of("y"));
        PipelineStage c = new RecordingStage("c", List.of("y"), List.of());
        DataflowPipeline pipeline = new DataflowPipeline("linear", List.of(c, a, b));

        pipeline.validate();
        assertThat(pipeline.topologicalOrder()).containsExactly("a", "b", "c");
    }

    @Test
    void topologicalOrderRespectsDiamondDependencies() {
        // a -> {b, c} -> d. Both b and c depend on a; d depends on b and c.
        PipelineStage a = new RecordingStage("a", List.of(), List.of("a-out"));
        PipelineStage b = new RecordingStage("b", List.of("a-out"), List.of("b-out"));
        PipelineStage c = new RecordingStage("c", List.of("a-out"), List.of("c-out"));
        PipelineStage d = new RecordingStage("d", List.of("b-out", "c-out"), List.of());
        DataflowPipeline pipeline = new DataflowPipeline("diamond", List.of(d, c, b, a));

        pipeline.validate();
        List<String> order = pipeline.topologicalOrder();

        // 'a' first, 'd' last; b and c in between (relative order unspecified).
        assertThat(order).hasSize(4);
        assertThat(order.get(0)).isEqualTo("a");
        assertThat(order.get(3)).isEqualTo("d");
        assertThat(order).contains("b", "c");
    }

    /**
     * A serializable stub stage that records its execution in {@link #EXECUTED}.
     * Named static class (not anonymous) so it survives Beam serialization.
     */
    static final class RecordingStage implements PipelineStage, Serializable {
        private static final long serialVersionUID = 1L;
        private final String name;
        @SuppressWarnings("serial")
        private final List<String> inputs;
        @SuppressWarnings("serial")
        private final List<String> outputs;

        RecordingStage(String name, List<String> inputs, List<String> outputs) {
            this.name = name;
            this.inputs = List.copyOf(inputs);
            this.outputs = List.copyOf(outputs);
        }

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
            EXECUTED.put(name, Boolean.TRUE);
        }
    }
}
