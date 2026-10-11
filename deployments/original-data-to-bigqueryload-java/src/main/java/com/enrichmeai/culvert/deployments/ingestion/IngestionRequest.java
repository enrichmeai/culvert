package com.enrichmeai.culvert.deployments.ingestion;

import java.util.Objects;

/**
 * Parameters for one {@link IngestionRunner#run} call — the Java-side
 * equivalent of the Python reference's {@code GenericPipelineOptions}
 * ({@code deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/options.py})
 * plus the GCS/BigQuery target fields carried by {@code GCPPipelineOptions}.
 *
 * @param runId       Unique run identifier (also used as the job-control key).
 * @param entity      Without a schema file, one of the built-in entities {@code customers},
 *                    {@code accounts}, {@code decision}, {@code applications} (see
 *                    {@link com.enrichmeai.culvert.deployments.ingestion.schema.GenericEntities}). With
 *                    one, only a label: it names the run's job, staging and error paths.
 * @param sourceUri   {@code gs://} (or other {@code BlobStore}-scheme) URI of the
 *                    HDR/TRL-enveloped CSV file to ingest.
 * @param extractDate Extract date, {@code yyyyMMdd} (mirrors the Python
 *                    {@code --extract_date} option).
 * @param targetTable Fully-qualified BigQuery ODP table
 *                    ({@code project.dataset.table} or {@code dataset.table}).
 * @param schemaUri   Optional: the entity schema file ({@code gs://…/<entity>.schema.yaml} or a
 *                    local path) the layout comes from. Null for a built-in entity.
 * @param schemaText  Optional: that file's text, already read. When set, the runner parses it
 *                    rather than reading {@code schemaUri} (which then only names it in messages):
 *                    a worker may not reach the place the launcher read it from.
 */
public record IngestionRequest(
        String runId,
        String entity,
        String sourceUri,
        String extractDate,
        String targetTable,
        String schemaUri,
        String schemaText) {

    public IngestionRequest {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(entity, "entity must not be null");
        Objects.requireNonNull(sourceUri, "sourceUri must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(targetTable, "targetTable must not be null");
    }

    /** A request for one of the built-in entities: no schema file. */
    public IngestionRequest(String runId, String entity, String sourceUri, String extractDate, String targetTable) {
        this(runId, entity, sourceUri, extractDate, targetTable, null, null);
    }
}
