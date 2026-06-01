package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.Pipeline;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link PipelineToDagSpec}.
 *
 * <p>Tests use test-doubles that implement full validation logic (mirroring
 * {@code DataflowPipeline}) so that orphan-input and cycle tests exercise
 * the real contract check, not a no-op stub.
 */
class PipelineToDagSpecTest {

    // -------------------------------------------------------------------------
    // Test doubles with real validation
    // -------------------------------------------------------------------------

    /**
     * Minimal {@link PipelineStage} backed by plain fields.
     */
    static final class SimpleStage implements PipelineStage {
        private final String name;
        private final List<String> inputs;
        private final List<String> outputs;

        SimpleStage(String name, List<String> inputs, List<String> outputs) {
            this.name = name;
            this.inputs = List.copyOf(inputs);
            this.outputs = List.copyOf(outputs);
        }

        @Override public String name() { return name; }
        @Override public List<String> inputs() { return inputs; }
        @Override public List<String> outputs() { return outputs; }
        @Override public void execute(RuntimeContext context) { /* no-op in tests */ }
    }

    /**
     * {@link Pipeline} test double that runs real validation logic identical
     * to {@code DataflowPipeline.validate()} — duplicate-name detection,
     * orphan-input detection, and DFS cycle detection.
     *
     * <p>Using a no-op validate() would let orphan-input tests pass vacuously
     * (the translator's Kahn sort cannot see orphans — they just become roots).
     */
    static final class TestPipeline implements Pipeline {
        private final String name;
        private final List<PipelineStage> stages;

        TestPipeline(String name, List<PipelineStage> stages) {
            this.name = name;
            this.stages = List.copyOf(stages);
        }

        @Override public String name() { return name; }
        @Override public List<PipelineStage> stages() { return stages; }

        @Override
        public void validate() {
            // 1. Stage names must be unique.
            Set<String> seenNames = new HashSet<>();
            for (PipelineStage stage : stages) {
                if (!seenNames.add(stage.name())) {
                    throw new IllegalStateException(
                            "Duplicate stage name: " + stage.name());
                }
            }

            // 2. Build output → producer map; detect duplicate outputs.
            Map<String, String> outputToProducer = new HashMap<>();
            for (PipelineStage stage : stages) {
                for (String output : stage.outputs()) {
                    String existing = outputToProducer.putIfAbsent(output, stage.name());
                    if (existing != null) {
                        throw new IllegalStateException(
                                "Output '" + output + "' produced by both '"
                                        + existing + "' and '" + stage.name() + "'");
                    }
                }
            }

            // 3. Every input must have a producer (no orphan inputs).
            for (PipelineStage stage : stages) {
                for (String input : stage.inputs()) {
                    String producer = outputToProducer.get(input);
                    if (producer == null) {
                        throw new IllegalStateException(
                                "Stage '" + stage.name() + "' has input '" + input
                                        + "' with no producer in the pipeline");
                    }
                    if (producer.equals(stage.name())) {
                        throw new IllegalStateException(
                                "Stage '" + stage.name() + "' depends on its own output");
                    }
                }
            }

            // 4. No cycles — DFS over the dependency graph.
            Map<String, List<String>> deps = buildDeps(outputToProducer);
            Set<String> visiting = new LinkedHashSet<>();
            Set<String> visited = new HashSet<>();
            for (PipelineStage stage : stages) {
                if (!visited.contains(stage.name())) {
                    detectCycle(stage.name(), deps, visiting, visited);
                }
            }
        }

        private Map<String, List<String>> buildDeps(Map<String, String> outputToProducer) {
            Map<String, List<String>> deps = new HashMap<>();
            for (PipelineStage stage : stages) {
                List<String> producers = new ArrayList<>();
                for (String input : stage.inputs()) {
                    String producer = outputToProducer.get(input);
                    if (producer != null && !producer.equals(stage.name())) {
                        producers.add(producer);
                    }
                }
                deps.put(stage.name(), producers);
            }
            return deps;
        }

        private static void detectCycle(String stageName,
                                        Map<String, List<String>> deps,
                                        Set<String> visiting,
                                        Set<String> visited) {
            if (visiting.contains(stageName)) {
                List<String> path = new ArrayList<>(visiting);
                path.add(stageName);
                int start = path.indexOf(stageName);
                List<String> cycle = path.subList(start, path.size());
                throw new IllegalStateException(
                        "Cycle detected in pipeline graph: "
                                + String.join(" -> ", cycle));
            }
            if (visited.contains(stageName)) return;
            visiting.add(stageName);
            for (String dep : deps.getOrDefault(stageName, List.of())) {
                detectCycle(dep, deps, visiting, visited);
            }
            visiting.remove(stageName);
            visited.add(stageName);
        }
    }

    // -------------------------------------------------------------------------
    // Helpers to build stage names / edges from a DagSpec
    // -------------------------------------------------------------------------

    private static Set<String> taskIds(DagSpec dag) {
        return dag.tasks().stream()
                .map(TaskSpec::taskId)
                .collect(Collectors.toSet());
    }

    private static List<String> taskIdOrder(DagSpec dag) {
        return dag.tasks().stream()
                .map(TaskSpec::taskId)
                .collect(Collectors.toList());
    }

    private static Set<String> edgeStrings(DagSpec dag) {
        return dag.edges().stream()
                .map(e -> e.fromTaskId() + " -> " + e.toTaskId())
                .collect(Collectors.toSet());
    }

    // -------------------------------------------------------------------------
    // Linear chain: A → B → C
    // -------------------------------------------------------------------------

    @Test
    void linearChain_producesCorrectTasksAndEdges() {
        // A produces "a_out"; B consumes "a_out" and produces "b_out"; C consumes "b_out".
        SimpleStage a = new SimpleStage("A", List.of(), List.of("a_out"));
        SimpleStage b = new SimpleStage("B", List.of("a_out"), List.of("b_out"));
        SimpleStage c = new SimpleStage("C", List.of("b_out"), List.of());

        Pipeline pipeline = new TestPipeline("linear", List.of(a, b, c));
        DagSpec dag = PipelineToDagSpec.translate(pipeline, "@daily");

        assertThat(dag.dagId()).isEqualTo("linear");
        assertThat(dag.schedule()).isEqualTo("@daily");
        assertThat(taskIds(dag)).containsExactlyInAnyOrder("A", "B", "C");
        assertThat(edgeStrings(dag))
                .containsExactlyInAnyOrder("A -> B", "B -> C");

        // Topological order: A before B before C.
        List<String> order = taskIdOrder(dag);
        assertThat(order.indexOf("A")).isLessThan(order.indexOf("B"));
        assertThat(order.indexOf("B")).isLessThan(order.indexOf("C"));
    }

    // -------------------------------------------------------------------------
    // Diamond: A → B, A → C, B → D, C → D
    // -------------------------------------------------------------------------

    @Test
    void diamondDependency_producesCorrectTasksEdgesAndOrder() {
        // A → (B, C) → D
        SimpleStage a = new SimpleStage("A", List.of(), List.of("a_out"));
        SimpleStage b = new SimpleStage("B", List.of("a_out"), List.of("b_out"));
        SimpleStage c = new SimpleStage("C", List.of("a_out"), List.of("c_out"));
        SimpleStage d = new SimpleStage("D", List.of("b_out", "c_out"), List.of());

        Pipeline pipeline = new TestPipeline("diamond", List.of(a, b, c, d));
        DagSpec dag = PipelineToDagSpec.translate(pipeline, "0 6 * * *");

        assertThat(dag.dagId()).isEqualTo("diamond");
        assertThat(dag.schedule()).isEqualTo("0 6 * * *");
        assertThat(taskIds(dag)).containsExactlyInAnyOrder("A", "B", "C", "D");

        // Edges
        assertThat(edgeStrings(dag))
                .containsExactlyInAnyOrder("A -> B", "A -> C", "B -> D", "C -> D");

        // Topological ordering constraints:
        List<String> order = taskIdOrder(dag);
        int iA = order.indexOf("A");
        int iB = order.indexOf("B");
        int iC = order.indexOf("C");
        int iD = order.indexOf("D");

        assertThat(iA).isLessThan(iB);
        assertThat(iA).isLessThan(iC);
        assertThat(iB).isLessThan(iD);
        assertThat(iC).isLessThan(iD);
    }

    // -------------------------------------------------------------------------
    // TaskSpec upstreams are populated correctly
    // -------------------------------------------------------------------------

    @Test
    void diamondDependency_taskSpecUpstreamsAreCorrect() {
        SimpleStage a = new SimpleStage("A", List.of(), List.of("a_out"));
        SimpleStage b = new SimpleStage("B", List.of("a_out"), List.of("b_out"));
        SimpleStage c = new SimpleStage("C", List.of("a_out"), List.of("c_out"));
        SimpleStage d = new SimpleStage("D", List.of("b_out", "c_out"), List.of());

        Pipeline pipeline = new TestPipeline("diamond2", List.of(a, b, c, d));
        DagSpec dag = PipelineToDagSpec.translate(pipeline, null);

        Map<String, TaskSpec> byId = new HashMap<>();
        for (TaskSpec t : dag.tasks()) {
            byId.put(t.taskId(), t);
        }

        assertThat(byId.get("A").upstreamTaskIds()).isEmpty();
        assertThat(byId.get("B").upstreamTaskIds()).containsExactly("A");
        assertThat(byId.get("C").upstreamTaskIds()).containsExactly("A");
        assertThat(byId.get("D").upstreamTaskIds()).containsExactlyInAnyOrder("B", "C");
    }

    // -------------------------------------------------------------------------
    // stageName mirrors taskId (identity mapping in this translator)
    // -------------------------------------------------------------------------

    @Test
    void stageName_equalsTaskId() {
        SimpleStage a = new SimpleStage("StageAlpha", List.of(), List.of("x"));
        SimpleStage b = new SimpleStage("StageBeta", List.of("x"), List.of());

        Pipeline pipeline = new TestPipeline("p", List.of(a, b));
        DagSpec dag = PipelineToDagSpec.translate(pipeline, null);

        for (TaskSpec t : dag.tasks()) {
            assertThat(t.stageName()).isEqualTo(t.taskId());
        }
    }

    // -------------------------------------------------------------------------
    // Rejection tests
    // -------------------------------------------------------------------------

    @Test
    void cycleInPipeline_isRejected() {
        // A → B → A is a cycle; simulate via a multi-node cycle.
        // A produces "a_out"; B consumes "a_out" and produces "b_out";
        // A also "consumes" "b_out" — but A's output was "a_out", so we need
        // to declare A's inputs as ["b_out"] to close the cycle.
        SimpleStage a = new SimpleStage("A", List.of("b_out"), List.of("a_out"));
        SimpleStage b = new SimpleStage("B", List.of("a_out"), List.of("b_out"));

        Pipeline pipeline = new TestPipeline("cyclic", List.of(a, b));

        assertThatThrownBy(() -> PipelineToDagSpec.translate(pipeline, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Cycle");
    }

    @Test
    void orphanInput_isRejected() {
        // B declares input "missing_out" which no stage produces.
        SimpleStage a = new SimpleStage("A", List.of(), List.of("a_out"));
        SimpleStage b = new SimpleStage("B", List.of("missing_out"), List.of());

        Pipeline pipeline = new TestPipeline("orphan", List.of(a, b));

        assertThatThrownBy(() -> PipelineToDagSpec.translate(pipeline, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no producer");
    }

    @Test
    void nullPipeline_throwsNullPointerException() {
        assertThatThrownBy(() -> PipelineToDagSpec.translate(null, "@daily"))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // DagSpec / TaskSpec value semantics
    // -------------------------------------------------------------------------

    @Test
    void dagSpec_valueEqualityAndHashCode() {
        SimpleStage a = new SimpleStage("X", List.of(), List.of("x_out"));
        SimpleStage b = new SimpleStage("Y", List.of("x_out"), List.of());

        Pipeline pipeline = new TestPipeline("eq-test", List.of(a, b));
        DagSpec dag1 = PipelineToDagSpec.translate(pipeline, "@weekly");
        DagSpec dag2 = PipelineToDagSpec.translate(pipeline, "@weekly");

        assertThat(dag1).isEqualTo(dag2);
        assertThat(dag1.hashCode()).isEqualTo(dag2.hashCode());
        assertThat(dag1.toString()).contains("eq-test");
    }

    @Test
    void taskSpec_valueEqualityAndHashCode() {
        TaskSpec t1 = new TaskSpec("t", "s", List.of("u1"), Map.of());
        TaskSpec t2 = new TaskSpec("t", "s", List.of("u1"), Map.of());

        assertThat(t1).isEqualTo(t2);
        assertThat(t1.hashCode()).isEqualTo(t2.hashCode());
        assertThat(t1.toString()).contains("t");
    }

    @Test
    void dagSpec_edge_valueEqualityAndHashCode() {
        DagSpec.Edge e1 = new DagSpec.Edge("from", "to");
        DagSpec.Edge e2 = new DagSpec.Edge("from", "to");

        assertThat(e1).isEqualTo(e2);
        assertThat(e1.hashCode()).isEqualTo(e2.hashCode());
        assertThat(e1.toString()).contains("from -> to");
    }

    // -------------------------------------------------------------------------
    // Single-stage pipeline (no edges)
    // -------------------------------------------------------------------------

    @Test
    void singleStage_noEdges() {
        SimpleStage a = new SimpleStage("Solo", List.of(), List.of("out"));
        Pipeline pipeline = new TestPipeline("solo", List.of(a));
        DagSpec dag = PipelineToDagSpec.translate(pipeline, null);

        assertThat(dag.tasks()).hasSize(1);
        assertThat(dag.edges()).isEmpty();
        assertThat(dag.tasks().get(0).upstreamTaskIds()).isEmpty();
    }
}
