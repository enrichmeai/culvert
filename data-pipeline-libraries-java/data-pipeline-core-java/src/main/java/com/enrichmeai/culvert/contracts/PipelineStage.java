package com.enrichmeai.culvert.contracts;

import java.util.List;

/**
 * A named, dependency-aware unit of work inside a {@link Pipeline}.
 *
 * <p>{@code inputs} and {@code outputs} reference other stage names by string.
 * The framework uses these to compute execution order and to validate that
 * every input has a producer.
 *
 * <p>Java mirror of the Python {@code PipelineStage} Protocol.
 */
public interface PipelineStage {

    /** Unique stage name within the pipeline. */
    String name();

    /** Names of upstream stages whose outputs this stage consumes. */
    List<String> inputs();

    /** Names of logical outputs this stage produces (for downstream stages to reference). */
    List<String> outputs();

    /**
     * Execute the stage.
     *
     * @param context The runtime context for this stage.
     */
    void execute(RuntimeContext context);
}
