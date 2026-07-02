package com.enrichmeai.culvert.deployments.ingestion.envelope;

/**
 * Parsed {@code TRL|RecordCount=<n>|Checksum=<value>} line.
 *
 * <p>Wire format ported from the Python reference implementation. See
 * {@code gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/file_management/hdr_trl/constants.py:9}:
 * {@code DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'}.
 *
 * @param recordCount The declared data-row count (excludes HDR/TRL and the CSV header row).
 * @param checksum    The declared checksum over the data lines (algorithm: md5, per the
 *                    Python {@code validate_checksum} default).
 * @param rawLine     The original line, for diagnostics.
 */
public record TrailerRecord(int recordCount, String checksum, String rawLine) {
}
