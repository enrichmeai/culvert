/**
 * Cloud-neutral orchestration layer: a scheduler-agnostic DAG model
 * ({@code DagSpec} / {@code TaskSpec}), a {@code Pipeline -> DagSpec}
 * translator, and scheduler-specific renderers.
 *
 * <p>This module is the orchestration successor described in the Sprint-11
 * epic. It depends only on the Culvert contracts and {@code java.util} — no
 * Beam, no Airflow, no GCP.
 *
 * <p>Key classes:
 * <ul>
 *   <li>{@link com.enrichmeai.culvert.orchestration.DagSpec} /
 *       {@link com.enrichmeai.culvert.orchestration.TaskSpec} — the
 *       cloud-neutral DAG model.</li>
 *   <li>{@link com.enrichmeai.culvert.orchestration.PipelineToDagSpec} —
 *       translates a {@code Pipeline} to a {@code DagSpec} (T11.1).</li>
 *   <li>{@link com.enrichmeai.culvert.orchestration.DagRenderer} — strategy
 *       interface for rendering a {@code DagSpec} to a target-specific
 *       artefact (T11.3).</li>
 *   <li>{@link com.enrichmeai.culvert.orchestration.AirflowDagRenderer} —
 *       renders a {@code DagSpec} to an Apache Airflow 2.9.x Python DAG
 *       file (T11.3).</li>
 *   <li>{@link com.enrichmeai.culvert.orchestration.ComposerDagRenderer} —
 *       renders a {@code DagSpec} to a Cloud Composer-targeted Python DAG
 *       file with Composer-specific packaging header (T11.3).</li>
 * </ul>
 *
 * <p>Sprint-11 deliverables (epic #46): T11.1 (model + translator) and
 * T11.3 (Airflow + Composer renderers) are both implemented in this package.
 */
package com.enrichmeai.culvert.orchestration;
