package com.enrichmeai.culvert.contracts;

import java.io.FileNotFoundException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Iterator;

/**
 * Object storage abstraction. Cloud-neutral by construction.
 *
 * <p>URIs are opaque strings ({@code gs://}, {@code s3://}, {@code abfs://}).
 * The framework does not parse them; implementations do. Implementations
 * should raise {@link FileNotFoundException} (wrapped where necessary) for
 * {@link #get(String)} / {@link #openInput(String)} against a missing object.
 *
 * <p>Java mirror of the Python {@code BlobStore} Protocol.
 */
public interface BlobStore {

    /** Return the full object bytes at {@code uri}. */
    byte[] get(String uri);

    /**
     * Open a streaming read handle on the object at {@code uri}.
     *
     * <p>Use for large objects where loading the full bytes into memory is
     * wasteful. Callers must close the stream.
     */
    InputStream openInput(String uri);

    /**
     * Open a streaming write handle for the object at {@code uri}.
     *
     * <p>Callers must close the stream to commit the write.
     */
    OutputStream openOutput(String uri);

    /** Write {@code data} to {@code uri}. Overwrites existing objects. */
    void put(String uri, byte[] data);

    /**
     * Yield object URIs under {@code prefix} in lexicographic order.
     *
     * <p>{@code prefix} is itself a URI (e.g. {@code gs://bucket/dir/}). The
     * yielded URIs are absolute.
     */
    Iterator<String> list(String prefix);

    /** Return true if an object exists at {@code uri}. */
    boolean exists(String uri);

    /** Delete the object at {@code uri}. Idempotent. */
    void delete(String uri);

    /**
     * Server-side copy from {@code src} to {@code dst}.
     *
     * <p>Within the same store this should be a metadata-only operation.
     * Cross-store copies ({@code gs://} to {@code s3://}) are out of scope;
     * implementations may throw {@link UnsupportedOperationException} for
     * foreign schemes.
     */
    void copy(String src, String dst);
}
