package com.enrichmeai.culvert.aws.s3;

import com.enrichmeai.culvert.contracttests.BlobStoreContractTest;
import com.enrichmeai.culvert.contracts.BlobStore;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectResponse;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link S3BlobStore}.
 *
 * <p>Extends {@link BlobStoreContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link S3BlobStore} so all inherited contract
 * methods execute without real AWS credentials or network. Mirrors
 * {@code GcsBlobStoreContractTest} in {@code data-pipeline-gcp-gcs-java}.
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension} so that stubs set up unconditionally in
 * {@link #store()} are not flagged as unnecessary by strict stubbing when
 * some tests (e.g. {@code nullArgumentsRejected}) exercise only the SUT's
 * argument validation and never touch the mocked client.
 *
 * <p>Sprint-21 deliverable (T21.1, issue #145).
 */
class S3BlobStoreContractTest extends BlobStoreContractTest {

    private static final String BUCKET = "contract-bucket";
    private static final String KNOWN_OBJECT = "contract/known-object.txt";
    private static final String MISSING_OBJECT = "contract/missing-object.txt";

    /** Full s3:// URI for the pre-populated object. */
    private static final String KNOWN_URI = "s3://" + BUCKET + "/" + KNOWN_OBJECT;

    /** Full s3:// URI that resolves to nothing. */
    private static final String MISSING_URI = "s3://" + BUCKET + "/" + MISSING_OBJECT;

    @Override
    protected BlobStore store() {
        S3Client client = mock(S3Client.class);

        // Known object — HeadObject succeeds, GetObject returns "hello".
        when(client.headObject(HeadObjectRequest.builder().bucket(BUCKET).key(KNOWN_OBJECT).build()))
                .thenReturn(HeadObjectResponse.builder().build());
        when(client.getObjectAsBytes(GetObjectRequest.builder().bucket(BUCKET).key(KNOWN_OBJECT).build()))
                .thenReturn(ResponseBytes.fromByteArray(
                        GetObjectResponse.builder().build(), "hello".getBytes()));

        // Missing object — HeadObject/GetObject raise NoSuchKeyException
        // (S3BlobStore maps this to `false` / UncheckedIOException respectively).
        when(client.headObject(HeadObjectRequest.builder().bucket(BUCKET).key(MISSING_OBJECT).build()))
                .thenThrow(NoSuchKeyException.builder().message("not found").build());

        // delete(missingUri): S3's DeleteObject API returns 204 regardless of
        // whether the key existed, so no exception stub is needed — a fresh
        // mock already returns a default DeleteObjectResponse.
        when(client.deleteObject(DeleteObjectRequest.builder().bucket(BUCKET).key(MISSING_OBJECT).build()))
                .thenReturn(DeleteObjectResponse.builder().build());

        return new S3BlobStore(client);
    }

    @Override
    protected String knownUri() {
        return KNOWN_URI;
    }

    @Override
    protected String missingUri() {
        return MISSING_URI;
    }
}
