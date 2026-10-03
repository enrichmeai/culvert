package com.enrichmeai.culvert.orchestration;

/**
 * Strategy interface for rendering a {@link DagSpec} into a deployable
 * artefact for a specific scheduler target.
 *
 * <p>Implementations must consume only {@link DagSpec}/{@link TaskSpec} —
 * they must not reach back into the {@link com.enrichmeai.culvert.contracts.Pipeline}
 * contract or any runtime dependency.
 *
 * <p>Known implementations:
 * <ul>
 *   <li>{@link AirflowDagRenderer} — emits a standalone Airflow 2.9.x
 *       Python DAG file.</li>
 *   <li>{@link ComposerDagRenderer} — emits a Cloud Composer-targeted DAG
 *       file (same DAG body with Composer-specific packaging header).</li>
 *   <li>{@link SubstrateDagRenderer} — emits a DAG whose tasks run on a chosen
 *       {@link ExecutionSubstrate}.</li>
 * </ul>
 *
 * <p>Every implementation validates gate predicates first ({@link StageGate#validate(DagSpec)}),
 * and either emits a gated task's runtime re-check or refuses the task. It never renders a gated
 * task without its check.
 *
 * <p>Sprint-11 deliverable: issue #63 (T11.3).
 */
public interface DagRenderer {

    /**
     * Render the given {@link DagSpec} into a target-specific string artefact.
     *
     * @param dagSpec the scheduler-agnostic DAG to render. Non-null.
     * @return the rendered artefact as a {@code String} (e.g. Python source
     *         for Airflow/Composer targets).
     * @throws NullPointerException if {@code dagSpec} is null.
     */
    String render(DagSpec dagSpec);
}
