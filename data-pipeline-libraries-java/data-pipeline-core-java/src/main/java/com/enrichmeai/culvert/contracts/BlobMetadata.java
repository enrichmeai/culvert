package com.enrichmeai.culvert.contracts;

import java.time.Instant;
import java.util.Collections;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * What a store knows about an object without reading it — the answer to
 * {@link BlobStore#head(String)}.
 *
 * <p>Exists for loaders that must decide whether an object has already been
 * taken: {@link BlobStore#list(String)} yields URIs only and
 * {@link BlobStore#exists(String)} a boolean, and neither says which
 * <em>version</em> of the object is there. The version is the store's
 * {@link #etag()}: it changes when the bytes do, so a loader keyed on
 * {@code (uri, etag)} skips what it has loaded and loads a republished object
 * as new, without a full read to find out.
 *
 * <p>Cloud-neutral: every field is one every serious store reports on a HEAD
 * (GCS object metadata, S3 {@code HeadObject}, Azure blob properties). The
 * ETag's <em>format</em> is the store's own — an MD5 on S3 single-part
 * uploads and on GCS, an opaque token elsewhere — so callers compare ETags
 * for equality within one store and never parse them.
 *
 * @param uri          The object's absolute URI, as asked for.
 * @param size         Size in bytes.
 * @param etag         The store's version token for these bytes. Never null;
 *                     may be empty if the store reports none.
 * @param lastModified When the object was last written, if the store reports it.
 * @param metadata     User-set custom metadata, as the store returns it; empty
 *                     when none. Unmodifiable.
 */
public record BlobMetadata(
        String uri,
        long size,
        String etag,
        Optional<Instant> lastModified,
        Map<String, String> metadata) {

    public BlobMetadata {
        Objects.requireNonNull(uri, "uri must not be null");
        Objects.requireNonNull(etag, "etag must not be null — pass an empty string for a store that reports none");
        Objects.requireNonNull(lastModified, "lastModified must not be null — pass Optional.empty()");
        Objects.requireNonNull(metadata, "metadata must not be null — pass an empty map");
        if (size < 0) {
            throw new IllegalArgumentException("size must not be negative: " + size);
        }
        metadata = Collections.unmodifiableMap(Map.copyOf(metadata));
    }
}
