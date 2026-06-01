package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.Pipeline;
import com.enrichmeai.culvert.contracts.PipelineStage;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Translates a validated {@link Pipeline} into a scheduler-agnostic
 * {@link DagSpec}.
 *
 * <p>The translation is purely structural:
 * <ol>
 *   <li>Calls {@link Pipeline#validate()} — any cycle or orphan-input
 *       violation surfaces as an {@link IllegalStateException} from the
 *       contract's own validation logic.</li>
 *   <li>Computes a topological execution order (Kahn's algorithm, ties
 *       broken by declaration order for determinism).</li>
 *   <li>Creates one {@link TaskSpec} per stage, in topological order.
 *       The task id equals the stage name; upstream task ids are the
 *       stage's input-producers.</li>
 *   <li>Builds an explicit {@link DagSpec.Edge} list from the same
 *       input/output dependency edges.</li>
 * </ol>
 *
 * <p>This class is cloud-neutral and has no engine-specific imports.
 * It depends only on {@code data-pipeline-core} and {@code java.util}.
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * DagSpec dag = PipelineToDagSpec.translate(myPipeline, "@daily");
 * }</pre>
 */
public final class PipelineToDagSpec {

    /** Utility class — no instances. */
    private PipelineToDagSpec() {}

    /**
     * Translate a {@link Pipeline} to a {@link DagSpec}.
     *
     * <p>The pipeline's {@link Pipeline#validate()} is called first;
     * violations propagate unchanged.
     *
     * <p>The dag id is set to the pipeline's {@link Pipeline#name()}; the
     * schedule is the caller-supplied string.
     *
     * @param pipeline Non-null, non-empty pipeline to translate. Its
     *                 {@code validate()} must not throw.
     * @param schedule Opaque schedule string for the target scheduler (e.g.
     *                 {@code "@daily"}, {@code "0 6 * * *"}). May be
     *                 {@code null} for manually-triggered DAGs.
     * @return An immutable {@link DagSpec} whose tasks are in topological
     *         order.
     * @throws NullPointerException  if {@code pipeline} is null.
     * @throws IllegalStateException if the pipeline fails validation
     *                               (cycle, orphan input, duplicate stage
     *                               name, etc.).
     */
    public static DagSpec translate(Pipeline pipeline, String schedule) {
        Objects.requireNonNull(pipeline, "pipeline must not be null");

        // 1. Validate — surfaces cycles, orphan inputs, duplicate names.
        pipeline.validate();

        List<PipelineStage> stages = pipeline.stages();

        // 2. Build output → producer index.
        Map<String, String> outputToProducer = new HashMap<>();
        for (PipelineStage stage : stages) {
            for (String output : stage.outputs()) {
                outputToProducer.put(output, stage.name());
            }
        }

        // 3. Build in-degree and dependents maps for Kahn's algorithm.
        //    edges: producer stage name → list of consumer stage names.
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

        // 4. Seed the queue with zero-in-degree stages in declaration order.
        Deque<String> ready = new ArrayDeque<>();
        for (PipelineStage stage : stages) {
            if (inDegree.get(stage.name()) == 0) {
                ready.add(stage.name());
            }
        }

        // 5. Kahn's topological sort.
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

        // Defensive guard — validate() already rejected cycles, but guard anyway.
        if (order.size() != stages.size()) {
            throw new IllegalStateException(
                    "Topological sort incomplete; the graph has a cycle");
        }

        // 6. Build stage-name → stage index for O(1) lookup.
        Map<String, PipelineStage> byName = new HashMap<>();
        for (PipelineStage stage : stages) {
            byName.put(stage.name(), stage);
        }

        // 7. Emit TaskSpecs + Edges.
        List<TaskSpec> tasks = new ArrayList<>(order.size());
        List<DagSpec.Edge> edges = new ArrayList<>();

        for (String stageName : order) {
            PipelineStage stage = byName.get(stageName);
            List<String> upstreams = new ArrayList<>();
            for (String input : stage.inputs()) {
                String producer = outputToProducer.get(input);
                if (producer != null && !producer.equals(stageName)) {
                    if (!upstreams.contains(producer)) {
                        upstreams.add(producer);
                        edges.add(new DagSpec.Edge(producer, stageName));
                    }
                }
            }
            tasks.add(new TaskSpec(stageName, stageName, upstreams, Map.of()));
        }

        return new DagSpec(pipeline.name(), schedule, tasks, edges);
    }
}
