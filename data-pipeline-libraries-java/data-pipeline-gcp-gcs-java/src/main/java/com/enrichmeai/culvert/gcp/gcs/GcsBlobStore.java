package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.google.api.gax.paging.Page;
import com.google.cloud.ReadChannel;
import com.google.cloud.WriteChannel;
import com.google.cloud.storage.Blob;
import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.BlobInfo;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageException;
import com.google.cloud.storage.StorageOptions;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.channels.Channels;
import java.util.Iterator;
import java.util.Objects;

/**
 * {@link BlobStore} implementation backed by Google Cloud Storage.
 *
 * <p>Wraps a {@link Storage} client and parses {@code gs://bucket/path}
 * URIs internally. Non-{@code gs://} URIs are rejected with
 * {@link IllegalArgumentException}, except for {@link #copy(String, String)}
 * cross-store copies, which raise {@link UnsupportedOperationException}
 * per the contract.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #GcsBlobStore()} — production: builds a default
 *       {@link Storage} client from Application Default Credentials.</li>
 *   <li>{@link #GcsBlobStore(Storage)} — tests and custom-credential wiring:
 *       inject a pre-built client (a Mockito mock in unit tests).</li>
 * </ul>
 *
 * <p>The no-arg constructor doubles as the {@link java.util.ServiceLoader}
 * entry point. No environment variables are required: GCS URIs carry the
 * bucket inline, so no default bucket or project ID is needed at
 * construction time. ADC supplies credentials.
 *
 * <p>This class is {@link AutoCloseable}; closing it closes the wrapped
 * client.
 *
 * <p>Sprint-1 deliverable for issue #7.
 */
public final class GcsBlobStore implements BlobStore, AutoCloseable {

    /** URI scheme this implementation accepts. */
    public static final String SCHEME = "gs://";

    private final Storage client;

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery.
     *
     * <p>Builds a default {@link Storage} client from Application Default
     * Credentials. The bucket is supplied per-call inside each
     * {@code gs://bucket/path} URI, so no environment variable is needed.
     */
    public GcsBlobStore() {
        this(StorageOptions.getDefaultInstance().getService());
    }

    /**
     * Constructor for tests and custom-credential wiring. Use this with a
     * Mockito mock of {@link Storage} to avoid touching real GCS from
     * unit tests.
     *
     * @param client Pre-built client. Required. Ownership transfers to
     *               this store — {@link #close()} will close it.
     * @throws NullPointerException if {@code client} is null.
     */
    public GcsBlobStore(Storage client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    @Override
    public byte[] get(String uri) {
        BlobId id = parse(uri);
        Blob blob = client.get(id);
        if (blob == null) {
            // Contract: missing object => FileNotFoundException (wrapped where
            // necessary). The contract API is unchecked, so wrap in
            // UncheckedIOException with FileNotFoundException as the cause.
            throw new UncheckedIOException(
                    new java.io.FileNotFoundException("Object not found: " + uri));
        }
        return blob.getContent();
    }

    @Override
    public InputStream openInput(String uri) {
        BlobId id = parse(uri);
        Blob blob = client.get(id);
        if (blob == null) {
            throw new UncheckedIOException(
                    new java.io.FileNotFoundException("Object not found: " + uri));
        }
        ReadChannel reader = blob.reader();
        return Channels.newInputStream(reader);
    }

    @Override
    public OutputStream openOutput(String uri) {
        BlobId id = parse(uri);
        BlobInfo info = BlobInfo.newBuilder(id).build();
        WriteChannel writer = client.writer(info);
        return Channels.newOutputStream(writer);
    }

    @Override
    public void put(String uri, byte[] data) {
        Objects.requireNonNull(data, "data must not be null");
        BlobId id = parse(uri);
        BlobInfo info = BlobInfo.newBuilder(id).build();
        client.create(info, data);
    }

    @Override
    public Iterator<String> list(String prefix) {
        ParsedUri parsed = parseUri(prefix);
        // The "path" portion of the prefix URI is itself a GCS object-name
        // prefix. Empty prefix lists the whole bucket.
        Page<Blob> page = parsed.objectName.isEmpty()
                ? client.list(parsed.bucket)
                : client.list(parsed.bucket, Storage.BlobListOption.prefix(parsed.objectName));
        Iterator<Blob> blobs = page.iterateAll().iterator();
        String bucket = parsed.bucket;
        return new Iterator<>() {
            @Override
            public boolean hasNext() {
                return blobs.hasNext();
            }

            @Override
            public String next() {
                Blob blob = blobs.next();
                return SCHEME + bucket + "/" + blob.getName();
            }
        };
    }

    @Override
    public boolean exists(String uri) {
        BlobId id = parse(uri);
        // A non-null Blob from Storage#get is enough; calling blob.exists()
        // would do a redundant second roundtrip.
        return client.get(id) != null;
    }

    @Override
    public void delete(String uri) {
        BlobId id = parse(uri);
        // Storage#delete returns false if the object did not exist. The
        // contract documents this method as idempotent, so a missing object
        // is not an error.
        try {
            client.delete(id);
        } catch (StorageException e) {
            if (e.getCode() == 404) {
                return;
            }
            throw e;
        }
    }

    @Override
    public void copy(String src, String dst) {
        // Cross-store copies (e.g. gs:// -> s3://) are out of scope per the
        // contract. Reject upfront so the caller gets the right exception
        // type instead of a confusing parse error.
        if (!isGcsUri(src) || !isGcsUri(dst)) {
            throw new UnsupportedOperationException(
                    "GcsBlobStore.copy only supports gs:// to gs:// copies; got "
                            + "src=" + src + ", dst=" + dst);
        }
        BlobId source = parse(src);
        BlobId target = parse(dst);
        // setTarget(BlobInfo) is the stable, long-documented overload.
        // setTarget(BlobId) exists in newer versions but BlobInfo is safer
        // across the libraries-bom range.
        Storage.CopyRequest request = Storage.CopyRequest.newBuilder()
                .setSource(source)
                .setTarget(BlobInfo.newBuilder(target).build())
                .build();
        client.copy(request).getResult();
    }

    @Override
    public void close() {
        try {
            client.close();
        } catch (Exception e) {
            // Storage#close throws Exception; surface IOExceptions as
            // unchecked so callers don't need to catch the broad signature.
            if (e instanceof IOException ioe) {
                throw new UncheckedIOException(ioe);
            }
            throw new RuntimeException(e);
        }
    }

    // ---- URI parsing ----

    private static boolean isGcsUri(String uri) {
        return uri != null && uri.startsWith(SCHEME);
    }

    private static BlobId parse(String uri) {
        ParsedUri parsed = parseUri(uri);
        if (parsed.objectName.isEmpty()) {
            throw new IllegalArgumentException(
                    "URI must include an object name: " + uri);
        }
        return BlobId.of(parsed.bucket, parsed.objectName);
    }

    private static ParsedUri parseUri(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        if (!uri.startsWith(SCHEME)) {
            throw new IllegalArgumentException(
                    "URI must start with " + SCHEME + ": " + uri);
        }
        String rest = uri.substring(SCHEME.length());
        int slash = rest.indexOf('/');
        String bucket;
        String objectName;
        if (slash < 0) {
            bucket = rest;
            objectName = "";
        } else {
            bucket = rest.substring(0, slash);
            objectName = rest.substring(slash + 1);
        }
        if (bucket.isEmpty()) {
            throw new IllegalArgumentException(
                    "URI must include a bucket: " + uri);
        }
        return new ParsedUri(bucket, objectName);
    }

    private static final class ParsedUri {
        final String bucket;
        final String objectName;

        ParsedUri(String bucket, String objectName) {
            this.bucket = bucket;
            this.objectName = objectName;
        }
    }
}
