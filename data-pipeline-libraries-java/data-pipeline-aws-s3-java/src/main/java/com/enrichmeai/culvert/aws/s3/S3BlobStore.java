package com.enrichmeai.culvert.aws.s3;

import com.enrichmeai.culvert.contracts.BlobStore;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.util.Iterator;
import java.util.Objects;

/**
 * AWS S3 implementation of {@link BlobStore}.
 *
 * <p><strong>Sprint-8 skeleton.</strong> One method ({@link #exists(String)})
 * is implemented and tested; the others throw
 * {@link UnsupportedOperationException} with a TODO pointing at the
 * post-sprint-8 expansion. This module exists as proof that the
 * cloud-neutral contract design works against a non-GCP cloud —
 * exhaustive implementation arrives in a later sprint.
 *
 * <p>Accepts {@code s3://bucket/key} URIs; rejects foreign schemes.
 */
public final class S3BlobStore implements BlobStore {

    public static final String SCHEME = "s3";

    private final S3Client client;

    public S3BlobStore(S3Client client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    @Override
    public boolean exists(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        S3Uri parsed = S3Uri.parse(uri);
        try {
            client.headObject(HeadObjectRequest.builder()
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
        throw post8("get");
    }

    @Override
    public InputStream openInput(String uri) {
        throw post8("openInput");
    }

    @Override
    public OutputStream openOutput(String uri) {
        throw post8("openOutput");
    }

    @Override
    public void put(String uri, byte[] data) {
        throw post8("put");
    }

    @Override
    public Iterator<String> list(String prefix) {
        throw post8("list");
    }

    @Override
    public void delete(String uri) {
        throw post8("delete");
    }

    @Override
    public void copy(String sourceUri, String destinationUri) {
        throw post8("copy");
    }

    private static UnsupportedOperationException post8(String method) {
        return new UnsupportedOperationException(
                method + "() not yet implemented in the sprint-8 S3 skeleton. "
                        + "See https://github.com/enrichmeai/gcp-pipeline-reference/issues/18 "
                        + "for the post-sprint-8 expansion plan.");
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
}
