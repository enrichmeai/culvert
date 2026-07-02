package com.enrichmeai.culvert.deployments.ingestion;

import java.util.Objects;

/**
 * Parameters for one {@link IngestionRunner#run} call — the Java-side
 * equivalent of the Python reference's {@code GenericPipelineOptions}
 * ({@code deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/options.py})
 * plus the GCS/BigQuery target fields carried by {@code GCPPipelineOptions}.
 *
 * @param runId       Unique run identifier (also used as the job-control key).
 * @param entity      One of {@code customers}, {@code accounts}, {@code decision},
 *                    {@code applications} (see {@link com.enrichmeai.culvert.deployments.ingestion.schema.GenericEntities}).
 * @param sourceUri   {@code gs://} (or other {@code BlobStore}-scheme) URI of the
 *                    HDR/TRL-enveloped CSV file to ingest.
 * @param extractDate Extract date, {@code yyyyMMdd} (mirrors the Python
 *                    {@code --extract_date} option).
 * @param targetTable Fully-qualified BigQuery ODP table
 *                    ({@code project.dataset.table} or {@code dataset.table}).
 */
public record IngestionRequest(
        String runId,
        String entity,
        String sourceUri,
        String extractDate,
        String targetTable) {

    public IngestionRequest {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(entity, "entity must not be null");
        Objects.requireNonNull(sourceUri, "sourceUri must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
    }
}
