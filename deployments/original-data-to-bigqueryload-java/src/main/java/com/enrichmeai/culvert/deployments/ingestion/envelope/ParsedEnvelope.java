package com.enrichmeai.culvert.deployments.ingestion.envelope;

import java.util.List;

/**
 * Result of successfully parsing an HDR/TRL-enveloped file: the header, the
 * trailer, and the data lines between them (CSV header row included, if
 * present, at index 0 of {@link #dataLines()} — callers that need to skip a
 * CSV header row do so explicitly, mirroring the Python
 * {@code ParsedFileMetadata.data_start_line} convention where the CSV header
 * is included in the data span).
 *
 * @param header    The parsed HDR line.
 * @param trailer   The parsed TRL line.
 * @param dataLines Every line strictly between HDR and TRL, in file order.
 */
public record ParsedEnvelope(HeaderRecord header, TrailerRecord trailer, List<String> dataLines) {

    public ParsedEnvelope {
        dataLines = List.copyOf(dataLines);
    }
}
