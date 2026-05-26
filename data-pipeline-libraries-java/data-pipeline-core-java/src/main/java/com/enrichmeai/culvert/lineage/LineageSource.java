package com.enrichmeai.culvert.lineage;

import java.util.Map;
import java.util.Optional;

/**
 * The upstream artefact lineage is being traced from.
 *
 * <p>Java equivalent of the Python {@code LineageSource} TypedDict
 * ({@code total=False}).
 *
 * @param type     The artefact type ({@code "file"}, {@code "table"}, {@code "topic"}).
 * @param uri      Opaque URI: {@code gs://...}, {@code s3://...}, {@code bigquery://...}.
 * @param schema   Optional schema description as an arbitrary attribute map.
 * @param metadata Optional metadata (record count, content hash, ...).
 */
public record LineageSource(
        String type,
        String uri,
        Optional<Map<String, Object>> schema,
        Optional<Map<String, Object>> metadata) {

    public LineageSource {
        if (type == null) throw new IllegalArgumentException("type");
        if (uri == null) throw new IllegalArgumentException("uri");
        if (schema == null) schema = Optional.empty();
        if (metadata == null) metadata = Optional.empty();
    }

    public static LineageSource of(String type, String uri) {
        return new LineageSource(type, uri, Optional.empty(), Optional.empty());
    }
}
