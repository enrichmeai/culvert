package com.enrichmeai.culvert.deployments.ingestion.envelope;

/**
 * Thrown when a file fails HDR/TRL envelope validation: missing/malformed
 * header or trailer, system-id/entity-type mismatch, record-count mismatch,
 * or checksum mismatch. Ports the error conditions raised by the retired
 * Python reference's {@code GenericFileValidator.validate} (removed 2026-07;
 * in git history at
 * {@code deployments/original-data-to-bigqueryload/src/data_ingestion/validation/file_validator.py:56-122}).
 */
public class EnvelopeParseException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public EnvelopeParseException(String message) {
        super(message);
    }
}
