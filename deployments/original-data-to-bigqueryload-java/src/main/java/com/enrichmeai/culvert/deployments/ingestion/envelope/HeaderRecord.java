package com.enrichmeai.culvert.deployments.ingestion.envelope;

/**
 * Parsed {@code HDR|<systemId>|<entityType>|<yyyyMMdd>} line.
 *
 * <p>Wire format ported from the Python reference implementation's
 * {@code gcp_pipeline_core.file_management.hdr_trl} library (not present in
 * Culvert Java — this deployment implements the parser locally). See
 * {@code gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/file_management/hdr_trl/constants.py:8}
 * for the source pattern:
 * {@code DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'}.
 *
 * @param systemId    The source system identifier (e.g. {@code "Generic"}).
 * @param entityType  The entity name (e.g. {@code "customers"}).
 * @param extractDate The extract date, {@code yyyyMMdd}.
 * @param rawLine     The original line, for diagnostics.
 */
public record HeaderRecord(String systemId, String entityType, String extractDate, String rawLine) {
}
