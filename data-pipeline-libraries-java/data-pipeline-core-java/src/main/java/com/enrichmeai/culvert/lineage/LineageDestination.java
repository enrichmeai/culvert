package com.enrichmeai.culvert.lineage;

import java.util.Map;
import java.util.Optional;

/**
 * The downstream artefact records were written to.
 *
 * <p>Java equivalent of the Python {@code LineageDestination} TypedDict
 * ({@code total=False}).
 *
 * @param type     Artefact type.
 * @param uri      Opaque URI.
 * @param schema   Optional schema description.
 * @param metadata Optional metadata.
 */
public record LineageDestination(
        String type,
        String uri,
        Optional<Map<String, Object>> schema,
        Optional<Map<String, Object>> metadata) {

    public LineageDestination {
        if (type == null) throw new IllegalArgumentException("type");
        if (uri == null) throw new IllegalArgumentException("uri");
        if (schema == null) schema = Optional.empty();
        if (metadata == null) metadata = Optional.empty();
    }

    public static LineageDestination of(String type, String uri) {
        return new LineageDestination(type, uri, Optional.empty(), Optional.empty());
    }
}
