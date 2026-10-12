package com.enrichmeai.culvert.schema;

import java.util.Optional;

/**
 * The HDR/TRL envelope settings an {@link EntitySchemaFile} may override. Each is empty when the
 * file does not set it, and the loader that reads the envelope applies its own default.
 *
 * @param systemId     The system id the HDR line must carry.
 * @param csvHeaderRow Whether the data between HDR and TRL starts with a CSV header row.
 */
public record EnvelopeSettings(Optional<String> systemId, Optional<Boolean> csvHeaderRow) {

    public EnvelopeSettings {
        if (systemId == null) systemId = Optional.empty();
        if (csvHeaderRow == null) csvHeaderRow = Optional.empty();
    }

    /** No overrides: every setting is the reader's default. */
    public static EnvelopeSettings defaults() {
        return new EnvelopeSettings(Optional.empty(), Optional.empty());
    }
}
