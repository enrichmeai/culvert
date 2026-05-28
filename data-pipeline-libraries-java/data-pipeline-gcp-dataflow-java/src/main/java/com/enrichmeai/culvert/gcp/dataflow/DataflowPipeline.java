package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.Pipeline;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.dataflow.DataflowRunner;
// Note: Beam 2.x uses `DataflowRunner` (not `DataflowPipelineRunner` —
// that was the old 1.x name kept around in pre-merge Beam).
import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/**
 * {@link Pipeline} implementation that bridges Culvert's topology contract
 * to Apache Beam's Dataflow runner.
 *
 * <p>The Culvert {@link Pipeline} contract is intentionally scheduler-
 * agnostic — it describes the DAG (name + stages + validate) but does not
 * mandate how stages execute. This adapter keeps that contract intact and
 * provides two utility methods on top:
 *
 * <ul>
 *   <li>{@link #buildBeam()} — converts the stage graph into an
 *       {@code org.apache.beam.sdk.Pipeline}. Each {@link PipelineStage} is
 *       wrapped in a Beam {@code Create.empty(...)} placeholder transform;
 *       full transform translation is sprint-4+ scope (it requires a
 *       runtime context that drives the stage's {@code execute} hook).</li>
 *   <li>{@link #runOnDataflow(DataflowPipelineOptions)} — submits the
 *       Beam pipeline to Google Cloud Dataflow via
 *       {@link DataflowRunner}.</li>
 * </ul>
 *
 * <p>Like the other GCP adapters in this framework, {@code DataflowPipeline}
 * does NOT implement {@link AutoCloseable} — the wrapped Beam Pipeline is
 * stateless after construction and the Dataflow runner manages its own
 * resources.
 *
 * <p>Sprint-2 deliverable for issue #25.
 */
public final class DataflowPipeline implements Pipeline {

    private final String name;
    private final List<PipelineStage> stages;

    /**
     * Construct a pipeline from a name and a list of stages.
     *
     * @param name   Unique pipeline name. Required, non-blank.
     * @param stages The stages in declaration order. The execution order
     *               is computed from the stage input/output edges by
     *               {@link #validate()}. Required, non-empty.
     * @throws NullPointerException     if either argument is null.
     * @throws IllegalArgumentException if {@code name} is blank or
     *                                  {@code stages} is empty.
     */
    public DataflowPipeline(String name, List<PipelineStage> stages) {
        Objects.requireNonNull(name, "name must not be null");
        Objects.requireNonNull(stages, "stages must not be null");
        if (name.isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }
        if (stages.isEmpty()) {
            throw new IllegalArgumentException("stages must not be empty");
        }
        this.name = name;
        this.stages = List.copyOf(stages);
    }

    @Override
    public String name() {
        return name;
    }

    @Override
    public List<PipelineStage> stages() {
        return stages;
    }

    /**
     * Validate the pipeline graph: every stage has a unique name; every
     * input references an output produced by an earlier stage; the graph
     * has no cycles.
     *
     * @throws IllegalStateException if the pipeline cannot run.
     */
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

        // 2. Every input must reference an output produced by some other
        //    stage (and not the same stage's own output).
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

        // 3. No cycles — DFS detection over the input dependency graph.
        Map<String, List<String>> dependencies = buildDependencyGraph(outputToProducer);
        Set<String> visiting = new LinkedHashSet<>();
        Set<String> visited = new HashSet<>();
        for (PipelineStage stage : stages) {
            if (!visited.contains(stage.name())) {
                detectCycle(stage.name(), dependencies, visiting, visited);
            }
        }
    }

    /**
     * Build a Beam {@link org.apache.beam.sdk.Pipeline} from this topology
     * with default {@link PipelineOptions} and a default {@link RuntimeContext}.
     *
     * <p>The default context is a {@link DefaultRuntimeContext} populated from
     * {@link AutoConfig#discover()} with {@code runId = "local-" +} a random
     * UUID, {@code environment = "local"}, and an empty config map. Use
     * {@link #buildBeam(PipelineOptions, RuntimeContext)} to supply your own.
     *
     * @return A configured Beam pipeline with one {@link StageTransform} per
     *         stage applied in topological order, ready to {@code run()}.
     */
    public org.apache.beam.sdk.Pipeline buildBeam() {
        return buildBeam(PipelineOptionsFactory.create());
    }

    /**
     * Build a Beam {@link org.apache.beam.sdk.Pipeline} with caller-supplied
     * options and a default {@link RuntimeContext} (see {@link #buildBeam()}
     * for the default's parameters).
     *
     * @param options Beam pipeline options. Required.
     */
    public org.apache.beam.sdk.Pipeline buildBeam(PipelineOptions options) {
        return buildBeam(options, defaultRuntimeContext());
    }

    /**
     * Build a Beam {@link org.apache.beam.sdk.Pipeline} with caller-supplied
     * options and runtime context.
     *
     * <p>Validates the topology, computes a topological execution order from
     * the stage input/output edges, then applies one {@link StageTransform}
     * per stage <em>in that order</em>. Declaration order is irrelevant — a
     * stage is wired after all the stages it depends on.
     *
     * <p>Each {@link StageTransform} is rooted at {@code PBegin}, so the stages
     * are independent roots in the Beam graph. The topological apply order
     * documents the dependency intent and is the anchor for richer
     * element-level data flow in a future sprint; today Beam schedules the
     * independent roots itself.
     *
     * @param options Beam pipeline options. Required.
     * @param context The runtime context handed to every stage's
     *                {@code execute}. Required; must be serializable to run on
     *                a distributed runner.
     */
    public org.apache.beam.sdk.Pipeline buildBeam(PipelineOptions options, RuntimeContext context) {
        Objects.requireNonNull(options, "options must not be null");
        Objects.requireNonNull(context, "context must not be null");
        validate();

        org.apache.beam.sdk.Pipeline beam = org.apache.beam.sdk.Pipeline.create(options);
        Map<String, PipelineStage> byName = new HashMap<>();
        for (PipelineStage stage : stages) {
            byName.put(stage.name(), stage);
        }
        for (String stageName : topologicalOrder()) {
            PipelineStage stage = byName.get(stageName);
            beam.apply(StageTransform.of(stage, context));
        }
        return beam;
    }

    /**
     * Convenience: submit this pipeline to Google Cloud Dataflow.
     *
     * <p>Sets the runner on the supplied options to
     * {@link DataflowRunner} (overriding whatever was previously
     * set), builds the Beam pipeline, and runs it.
     *
     * @param options Dataflow-specific options carrying {@code project},
     *                {@code region}, {@code stagingLocation}, etc. Required.
     * @return The Beam {@link PipelineResult} from
     *         {@code pipeline.run()} — typically a {@code DataflowPipelineJob}
     *         whose {@code waitUntilFinish()} blocks for completion.
     */
    public PipelineResult runOnDataflow(DataflowPipelineOptions options) {
        return runOnDataflow(options, defaultRuntimeContext());
    }

    /**
     * Convenience: submit this pipeline to Google Cloud Dataflow with a
     * caller-supplied runtime context.
     *
     * @param options Dataflow-specific options. Required.
     * @param context The runtime context handed to every stage. Required.
     * @return The Beam {@link PipelineResult} from {@code pipeline.run()}.
     */
    public PipelineResult runOnDataflow(DataflowPipelineOptions options, RuntimeContext context) {
        Objects.requireNonNull(options, "options must not be null");
        Objects.requireNonNull(context, "context must not be null");
        options.setRunner(DataflowRunner.class);
        org.apache.beam.sdk.Pipeline beam = buildBeam(options, context);
        return beam.run();
    }

    // --- helpers -----------------------------------------------------------

    /**
     * The default {@link RuntimeContext} backing the no-context
     * {@code buildBeam}/{@code runOnDataflow} overloads: a
     * {@link DefaultRuntimeContext} from {@link AutoConfig#discover()} with a
     * generated {@code runId}, {@code environment = "local"}, and an empty
     * config map.
     */
    private static RuntimeContext defaultRuntimeContext() {
        return DefaultRuntimeContext.fromAutoConfig(
                "local-" + UUID.randomUUID(),
                "local",
                Map.of(),
                AutoConfig.discover());
    }

    /**
     * Compute a topological execution order over the stage dependency graph
     * using Kahn's algorithm. {@link #validate()} has already proven the graph
     * is acyclic, so this always succeeds. Ties (stages with no remaining
     * dependencies) are broken by declaration order for determinism.
     *
     * @return Stage names, dependencies before dependents.
     */
    private List<String> topologicalOrder() {
        Map<String, String> outputToProducer = new HashMap<>();
        for (PipelineStage stage : stages) {
            for (String output : stage.outputs()) {
                outputToProducer.put(output, stage.name());
            }
        }
        // edges: producer -> consumers; inDegree: # of producers a stage waits on.
        Map<String, List<String>> dependents = new HashMap<>();
        Map<String, Integer> inDegree = new HashMap<>();
        for (PipelineStage stage : stages) {
            inDegree.putIfAbsent(stage.name(), 0);
            dependents.putIfAbsent(stage.name(), new ArrayList<>());
        }
        for (PipelineStage stage : stages) {
            for (String input : stage.inputs()) {
                String producer = outputToProducer.get(input);
                if (producer != null && !producer.equals(stage.name())) {
                    dependents.get(producer).add(stage.name());
                    inDegree.merge(stage.name(), 1, Integer::sum);
                }
            }
        }
        // Seed the queue with zero-in-degree stages in declaration order.
        Deque<String> ready = new ArrayDeque<>();
        for (PipelineStage stage : stages) {
            if (inDegree.get(stage.name()) == 0) {
                ready.add(stage.name());
            }
        }
        List<String> order = new ArrayList<>(stages.size());
        while (!ready.isEmpty()) {
            String current = ready.poll();
            order.add(current);
            for (String dependent : dependents.get(current)) {
                if (inDegree.merge(dependent, -1, Integer::sum) == 0) {
                    ready.add(dependent);
                }
            }
        }
        if (order.size() != stages.size()) {
            // Unreachable: validate() rejects cycles. Defensive guard only.
            throw new IllegalStateException(
                    "Topological sort incomplete; the graph has a cycle");
        }
        return order;
    }

    private Map<String, List<String>> buildDependencyGraph(
            Map<String, String> outputToProducer) {
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
                                    Map<String, List<String>> dependencies,
                                    Set<String> visiting,
                                    Set<String> visited) {
        if (visiting.contains(stageName)) {
            List<String> path = new ArrayList<>(visiting);
            path.add(stageName);
            // Trim to the cycle's start.
            int start = path.indexOf(stageName);
            List<String> cycle = path.subList(start, path.size());
            throw new IllegalStateException(
                    "Cycle detected in pipeline graph: "
                            + String.join(" -> ", cycle));
        }
        if (visited.contains(stageName)) {
            return;
        }
        visiting.add(stageName);
        for (String dep : dependencies.getOrDefault(stageName, Collections.emptyList())) {
            detectCycle(dep, dependencies, visiting, visited);
        }
        visiting.remove(stageName);
        visited.add(stageName);
    }
}
