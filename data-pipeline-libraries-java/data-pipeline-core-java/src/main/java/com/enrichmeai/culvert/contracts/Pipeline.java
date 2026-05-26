package com.enrichmeai.culvert.contracts;

import java.util.List;

/**
 * Composition of stages, scheduler-agnostic.
 *
 * <p>The pipeline does not know what runtime it will execute on; the runtime
 * (a Composer DAG, a Dataflow Flex template, a local in-process runner, a
 * future AWS Step Functions execution) is responsible for picking it up and
 * scheduling its stages.
 *
 * <p>Java mirror of the Python {@code Pipeline} Protocol.
 */
public interface Pipeline {

    /** Unique pipeline name. */
    String name();

    /** The stages, in declaration order. The execution order is computed from input/output edges. */
    List<PipelineStage> stages();

    /**
     * Check the graph (no orphan inputs, no cycles, every stage's inputs are
     * produced by an earlier stage).
     *
     * @throws IllegalStateException if the pipeline cannot run.
     */
    void validate();
}
