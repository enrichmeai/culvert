package com.enrichmeai.culvert.jobcontrol;

/**
 * Where in the pipeline a failure occurred. Used to drive retry/quarantine
 * routing — for example, {@link #VALIDATION} failures route to a dead-letter
 * queue rather than triggering a retry.
 *
 * <p>Mirrors the Python {@code data_pipeline_core.job_control_api.types.FailureStage}.
 */
public enum FailureStage {
    INGESTION("ingestion"),
    VALIDATION("validation"),
    TRANSFORMATION("transformation"),
    LOAD("load"),
    RECONCILIATION("reconciliation"),
    UNKNOWN("unknown");

    private final String value;

    FailureStage(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}
