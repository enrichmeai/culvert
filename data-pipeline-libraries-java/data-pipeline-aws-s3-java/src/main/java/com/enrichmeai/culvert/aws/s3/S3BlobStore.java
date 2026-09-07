package com.enrichmeai.culvert.aws.s3;

import com.enrichmeai.culvert.autoconfig.ProviderAvailability;
import com.enrichmeai.culvert.contracts.BlobStore;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Response;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Object;

import java.io.ByteArrayOutputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.URI;
import java.util.Iterator;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * AWS S3 implementation of {@link BlobStore}.
 *
 * <p>Wraps an AWS SDK v2 {@link S3Client} and parses {@code s3://bucket/key}
 * URIs internally, mirroring the behaviour of
 * {@code com.enrichmeai.culvert.gcp.gcs.GcsBlobStore}: a missing object on
 * {@link #get(String)} / {@link #openInput(String)} raises a
 * {@link FileNotFoundException} (wrapped in {@link UncheckedIOException}
 * since the contract is unchecked); {@link #delete(String)} is idempotent;
 * {@link #copy(String, String)} requires both URIs to use the {@value
 * #SCHEME} scheme; a {@code null} URI raises {@link NullPointerException};
 * a foreign scheme raises {@link IllegalArgumentException}.
 *
 * <h2>{@link #openOutput(String)} — buffer-and-put-on-close</h2>
 *
 * <p>Unlike GCS, S3 has no native streaming-write API without the
 * multipart-upload protocol (multiple HTTP requests coordinated by an
 * upload id). To keep this adapter simple, {@link #openOutput(String)}
 * returns an in-memory {@link ByteArrayOutputStream}-backed stream that
 * issues a single {@code PutObject} call when the caller closes it. This is
 * the same tradeoff most "simple" S3 SDK wrappers make; it is fine for the
 * pipeline's object sizes (config, manifests, small extracts) but is not
 * suitable for multi-gigabyte streaming writes. If that need arises, add a
 * multipart-upload-backed {@link OutputStream} as a follow-up — the
 * {@link BlobStore} contract does not change either way.
 *
 * <p>Post-sprint-8 expansion (issue #18): all seven previously-stubbed
 * methods ({@link #get}, {@link #openInput}, {@link #openOutput},
 * {@link #put}, {@link #list}, {@link #delete}, {@link #copy}) are now
 * implemented; only {@link #exists(String)} predates this change.
 */
public final class S3BlobStore implements BlobStore, ProviderAvailability {

    public static final String SCHEME = "s3";

    /** Cloud-family selector. Environment variable first, system property as the test hook. */
    static final String ENV_CULVERT_CLOUD = "CULVERT_CLOUD";
    static final String SYSPROP_CULVERT_CLOUD = "culvert.cloud";

    /**
     * {@code null} only for an instance built by the no-arg (ServiceLoader) constructor,
     * which defers client creation to first use so that construction itself never throws.
     * Guarded by {@code this} on the lazy path.
     */
    private volatile S3Client client;

    public S3BlobStore(S3Client client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    /**
     * No-arg constructor for worker-side auto-config reconstruction, gated on
     * {@code CULVERT_CLOUD=aws}: fat jars can carry both cloud families, and the selector
     * makes it deterministic which family's adapters are candidates.
     *
     * <p><strong>This constructor does not throw when the gate is closed.</strong> Declining
     * by throwing is what let one adapter truncate the whole provider list
     * ({@code AutoConfig.loadServiceList}'s {@code catch (Throwable ignored)}); the gate now
     * reports itself through {@link #isAvailable()} instead, so {@code AutoConfig} drops this
     * provider from the candidate set without losing any other. Story 1.1, AC 4.
     *
     * <p>Client creation is therefore deferred to first use — region and credentials come
     * from the AWS default chains at that point. Calling a {@link BlobStore} method on an
     * instance built this way while the gate is closed still fails loudly with
     * {@link IllegalStateException}: being unavailable means "do not select me", not
     * "silently do nothing".
     */
    public S3BlobStore() {
        this.client = null;
    }

    /**
     * {@code false} when the {@code CULVERT_CLOUD} selector does not name AWS, so that
     * auto-config does not treat this adapter as a candidate on a non-AWS classpath.
     * Always {@code true} for an instance built with an explicit {@link S3Client}.
     */
    @Override
    public boolean isAvailable() {
        return client != null || awsSelected();
    }

    /** The S3 client, created on first use for a no-arg (ServiceLoader) instance. */
    private S3Client client() {
        S3Client existing = this.client;
        if (existing != null) {
            return existing;
        }
        synchronized (this) {
            if (this.client == null) {
                if (!awsSelected()) {
                    throw new IllegalStateException(
                            "AWS adapters are gated to " + ENV_CULVERT_CLOUD
                                    + "=aws; current selector: " + cloudSelector());
                }
                this.client = S3Client.create();
            }
            return this.client;
        }
    }

    private static boolean awsSelected() {
        String cloud = cloudSelector();
        return cloud != null && cloud.equalsIgnoreCase("aws");
    }

    private static String cloudSelector() {
        String cloud = System.getenv(ENV_CULVERT_CLOUD);
        if (cloud == null || cloud.isBlank()) {
            cloud = System.getProperty(SYSPROP_CULVERT_CLOUD);
        }
        return (cloud == null || cloud.isBlank()) ? null : cloud;
    }

    @Override
    public boolean exists(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        try {
            client().headObject(HeadObjectRequest.builder()
                    .bucket(parsed.bucket())
                    .key(parsed.key())
                    .build());
            return true;
        } catch (NoSuchKeyException e) {
            return false;
        } catch (SdkException e) {
            // Permission errors, network errors, etc. propagate.
            if (e.getMessage() != null && e.getMessage().contains("404")) {
                return false;
            }
            throw e;
        }
    }

    @Override
    public byte[] get(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        try {
            return client().getObjectAsBytes(GetObjectRequest.builder()
                    .bucket(parsed.bucket())
                    .key(parsed.key())
                    .build())
                    .asByteArray();
        } catch (NoSuchKeyException e) {
            throw new UncheckedIOException(
                    new FileNotFoundException("Object not found: " + uri));
        }
    }

    @Override
    public InputStream openInput(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        try {
            ResponseInputStream<GetObjectResponse> response = client().getObject(GetObjectRequest.builder()
                    .bucket(parsed.bucket())
                    .key(parsed.key())
                    .build());
            return response;
        } catch (NoSuchKeyException e) {
            throw new UncheckedIOException(
                    new FileNotFoundException("Object not found: " + uri));
        }
    }

    @Override
    public OutputStream openOutput(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        // S3 has no streaming-write API without multipart upload. Buffer the
        // bytes in memory and issue a single PutObject on close() — see the
        // class Javadoc for the tradeoff and when to revisit it.
        return new ByteArrayOutputStream() {
            private boolean closed;

            @Override
            public void close() throws IOException {
                if (closed) {
                    return;
                }
                closed = true;
                super.close();
                client().putObject(PutObjectRequest.builder()
                        .bucket(parsed.bucket())
                        .key(parsed.key())
                        .build(), RequestBody.fromBytes(toByteArray()));
            }
        };
    }

    @Override
    public void put(String uri, byte[] data) {
        Objects.requireNonNull(uri, "uri must not be null");
        Objects.requireNonNull(data, "data must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        client().putObject(PutObjectRequest.builder()
                .bucket(parsed.bucket())
                .key(parsed.key())
                .build(), RequestBody.fromBytes(data));
    }

    @Override
    public Iterator<String> list(String prefix) {
        Objects.requireNonNull(prefix, "prefix must not be null");
        ListPrefix parsed = ListPrefix.parse(prefix);
        return new ListObjectsV2Iterator(parsed.bucket(), parsed.objectPrefix());
    }

    /**
     * Lazily pages through {@code ListObjectsV2}, fetching the next page only
     * once the current page is exhausted. Manual pagination (rather than
     * {@link S3Client#listObjectsV2Paginator}) keeps this adapter's only
     * client calls to plain request/response methods, which is what a mocked
     * {@link S3Client} in unit tests can stub directly.
     */
    private final class ListObjectsV2Iterator implements Iterator<String> {
        private final String bucket;
        private final String objectPrefix;
        private Iterator<S3Object> currentPage;
        private String nextContinuationToken;
        private boolean exhausted;

        ListObjectsV2Iterator(String bucket, String objectPrefix) {
            this.bucket = bucket;
            this.objectPrefix = objectPrefix;
            fetchNextPage();
        }

        private void fetchNextPage() {
            ListObjectsV2Request.Builder builder = ListObjectsV2Request.builder()
                    .bucket(bucket)
                    .prefix(objectPrefix);
            if (nextContinuationToken != null) {
                builder.continuationToken(nextContinuationToken);
            }
            ListObjectsV2Response response = client().listObjectsV2(builder.build());
            currentPage = response.contents().iterator();
            nextContinuationToken = Boolean.TRUE.equals(response.isTruncated())
                    ? response.nextContinuationToken()
                    : null;
            exhausted = nextContinuationToken == null;
        }

        @Override
        public boolean hasNext() {
            while (!currentPage.hasNext() && !exhausted) {
                fetchNextPage();
            }
            return currentPage.hasNext();
        }

        @Override
        public String next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            S3Object object = currentPage.next();
            return SCHEME + "://" + bucket + "/" + object.key();
        }
    }

    @Override
    public void delete(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        // DeleteObject is idempotent by design in the S3 API itself: it
        // returns 204 whether or not the key existed, so there is no 404 to
        // swallow here (unlike GcsBlobStore.delete).
        client().deleteObject(DeleteObjectRequest.builder()
                .bucket(parsed.bucket())
                .key(parsed.key())
                .build());
    }

    @Override
    public void copy(String sourceUri, String destinationUri) {
        Objects.requireNonNull(sourceUri, "sourceUri must not be null");
        Objects.requireNonNull(destinationUri, "destinationUri must not be null");
        S3Uri source = S3Uri.parse(sourceUri);
        S3Uri destination = S3Uri.parse(destinationUri);
        client().copyObject(CopyObjectRequest.builder()
                .sourceBucket(source.bucket())
                .sourceKey(source.key())
                .destinationBucket(destination.bucket())
                .destinationKey(destination.key())
                .build());
    }

    /** Helper: parse an {@code s3://bucket/key} URI into ({@code bucket}, {@code key}). */
    record S3Uri(String bucket, String key) {
        static S3Uri parse(String raw) {
            URI uri = URI.create(raw);
            if (!SCHEME.equals(uri.getScheme())) {
                throw new IllegalArgumentException(
                        "S3BlobStore only accepts s3:// URIs, got " + raw);
            }
            String bucket = uri.getHost();
            if (bucket == null || bucket.isBlank()) {
                throw new IllegalArgumentException("URI missing bucket: " + raw);
            }
            String key = uri.getPath();
            if (key == null || key.isBlank() || "/".equals(key)) {
                throw new IllegalArgumentException("URI missing object key: " + raw);
            }
            // Strip leading slash from path -> S3 key.
            return new S3Uri(bucket, key.startsWith("/") ? key.substring(1) : key);
        }
    }

    /**
     * Helper: parse an {@code s3://bucket[/prefix]} listing prefix into
     * ({@code bucket}, {@code objectPrefix}).
     *
     * <p>Unlike {@link S3Uri}, the object-name portion may be empty (list the
     * whole bucket) — {@link #list(String)} is the only caller.
     */
    record ListPrefix(String bucket, String objectPrefix) {
        static ListPrefix parse(String raw) {
            URI uri = URI.create(raw);
            if (!SCHEME.equals(uri.getScheme())) {
                throw new IllegalArgumentException(
                        "S3BlobStore only accepts s3:// URIs, got " + raw);
            }
            String bucket = uri.getHost();
            if (bucket == null || bucket.isBlank()) {
                throw new IllegalArgumentException("URI missing bucket: " + raw);
            }
            String path = uri.getPath();
            String objectPrefix = (path == null || "/".equals(path)) ? "" : path;
            // Strip leading slash from path -> S3 key prefix.
            if (objectPrefix.startsWith("/")) {
                objectPrefix = objectPrefix.substring(1);
            }
            return new ListPrefix(bucket, objectPrefix);
        }
    }
}
