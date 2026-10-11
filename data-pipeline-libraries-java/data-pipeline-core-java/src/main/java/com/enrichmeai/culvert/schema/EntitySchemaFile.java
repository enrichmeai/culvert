package com.enrichmeai.culvert.schema;

import java.util.List;
import java.util.Objects;

/**
 * One entity's layout, as an {@link EntitySchemas entity schema file} describes it: the schema
 * the rows are validated and loaded against, the file's column headers in order, and any
 * envelope settings that differ from the default.
 *
 * <p>Mirrors the Python {@code EntitySchemaFile}.
 *
 * @param schema   The entity schema; its name is the file's {@code entity}.
 * @param headers  The file's column headers, in order. Each names a field of {@code schema}.
 * @param envelope Envelope overrides; empty settings when the file has none.
 */
public record EntitySchemaFile(EntitySchema schema, List<String> headers, EnvelopeSettings envelope) {

    public EntitySchemaFile {
        Objects.requireNonNull(schema, "schema");
        Objects.requireNonNull(headers, "headers");
        headers = List.copyOf(headers);
        if (envelope == null) envelope = EnvelopeSettings.defaults();
    }
}
