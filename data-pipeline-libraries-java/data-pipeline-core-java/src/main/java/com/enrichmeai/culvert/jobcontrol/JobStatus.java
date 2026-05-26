package com.enrichmeai.culvert.jobcontrol;

/**
 * Lifecycle states of a pipeline job.
 *
 * <p>Mirrors the Python {@code data_pipeline_core.job_control_api.types.JobStatus}.
 * Enum string values match the Python enum's so a job record serialised by
 * either implementation deserialises in the other.
 */
public enum JobStatus {
    CREATED("created"),
    RUNNING("running"),
    SUCCEEDED("succeeded"),
    FAILED("failed"),
    RETRYING("retrying"),
    CANCELLED("cancelled");

    private final String value;

    JobStatus(String value) {
        this.value = value;
    }

    /** The wire-format string. Use this when serialising to JSON, BigQuery rows, etc. */
    public String getValue() {
        return value;
    }
}
