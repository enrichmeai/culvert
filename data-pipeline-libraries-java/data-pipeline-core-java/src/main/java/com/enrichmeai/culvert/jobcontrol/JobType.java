package com.enrichmeai.culvert.jobcontrol;

/**
 * Type of pipeline job. Drives status-aggregation logic in the repository
 * (e.g. an FDP transformation job depends on the corresponding ingestion job
 * completing successfully).
 *
 * <p>Mirrors the Python {@code data_pipeline_core.job_control_api.types.JobType}.
 */
public enum JobType {
    INGESTION("ingestion"),
    TRANSFORMATION("transformation"),
    RECONCILIATION("reconciliation"),
    BACKFILL("backfill");

    private final String value;

    JobType(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}
