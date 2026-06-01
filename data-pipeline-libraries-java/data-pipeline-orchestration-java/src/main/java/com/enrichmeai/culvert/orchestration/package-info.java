/**
 * Cloud-neutral orchestration layer: a scheduler-agnostic DAG model
 * ({@code DagSpec} / {@code TaskSpec}) and a {@code Pipeline -> DagSpec}
 * translator.
 *
 * <p>This module is the orchestration successor described in the Sprint-11
 * epic. It depends only on the Culvert contracts and {@code java.util} — no
 * Beam, no Airflow, no GCP. Engine-specific renderers (Airflow / Cloud
 * Composer) and job-control wiring live in later Sprint-11 tickets and build
 * on the model defined here.
 *
 * <p>Sprint-11 deliverable (epic #46): T11.1 model + translator scaffolds this
 * package.
 */
package com.enrichmeai.culvert.orchestration;
