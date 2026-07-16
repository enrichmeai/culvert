package com.enrichmeai.culvert.deployments.cdcstreaming;

/**
 * Readable CDC operation classification, mirroring the Python
 * {@code cdc_operation} string values produced by
 * {@code streaming_pipeline.pipeline.cdc_parser.ParseCDCEventDoFn} (see
 * deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/cdc_parser.py:73-91).
 *
 * <p>Debezium's {@code op} field uses single-letter codes:
 * {@code c}=create, {@code u}=update, {@code d}=delete, {@code r}=read
 * (snapshot). Any other value (schema-change events, etc.) is not a data
 * event and is skipped upstream — there is no {@code UNKNOWN} case reachable
 * from {@link CdcEventParser#parse(String)}.
 */
public enum CdcOperation {
    INSERT,
    UPDATE,
    DELETE,
    SNAPSHOT
}
