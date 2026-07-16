package com.enrichmeai.culvert.azure.blob;

import com.azure.storage.blob.BlobClient;
import com.azure.storage.blob.BlobContainerClient;
import com.azure.storage.blob.BlobServiceClient;
import com.enrichmeai.culvert.contracts.BlobStore;

import java.io.InputStream;
import java.io.OutputStream;
import java.util.Iterator;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Azure Blob Storage implementation of {@link BlobStore}.
 *
 * <p><strong>Sprint-8 skeleton.</strong> One method ({@link #exists(String)})
 * is implemented and tested; the others throw
 * {@link UnsupportedOperationException}. Proof of the cloud-neutral
 * design across non-GCP clouds.
 *
 * <p>Accepts {@code abfs://container@account.dfs.core.windows.net/path}
 * URIs (the Azure Data Lake Storage Gen2 form) per
 * {@code data-pipeline-core}'s convention.
 */
public final class AzureBlobStore implements BlobStore {

    public static final String SCHEME = "abfs";

    // abfs://<container>@<account>.dfs.core.windows.net/<path>
    private static final Pattern ABFS_URI = Pattern.compile(
            "abfs://([^@]+)@([^.]+)\\.dfs\\.core\\.windows\\.net/(.+)$"
    );

    private final BlobServiceClient serviceClient;

    public AzureBlobStore(BlobServiceClient serviceClient) {
        this.serviceClient = Objects.requireNonNull(serviceClient, "serviceClient must not be null");
    }

    @Override
    public boolean exists(String uri) {
        Objects.requireNonNull(uri, "uri must not be null");
        AbfsUri parsed = AbfsUri.parse(uri);
        BlobContainerClient container = serviceClient.getBlobContainerClient(parsed.container());
        BlobClient blob = container.getBlobClient(parsed.path());
        return Boolean.TRUE.equals(blob.exists());
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
                method + "() not yet implemented in the sprint-8 Azure Blob skeleton. "
                        + "See https://github.com/enrichmeai/culvert/issues/18 "
                        + "for the post-sprint-8 expansion plan.");
    }

    /** Helper: parse an abfs:// URI. */
    record AbfsUri(String container, String account, String path) {
        static AbfsUri parse(String raw) {
            if (raw == null) {
                throw new IllegalArgumentException("URI must not be null");
            }
            Matcher m = ABFS_URI.matcher(raw);
            if (!m.matches()) {
                throw new IllegalArgumentException(
                        "AzureBlobStore only accepts abfs://<container>@<account>.dfs.core.windows.net/<path> URIs, got " + raw);
            }
            return new AbfsUri(m.group(1), m.group(2), m.group(3));
        }
    }
}
