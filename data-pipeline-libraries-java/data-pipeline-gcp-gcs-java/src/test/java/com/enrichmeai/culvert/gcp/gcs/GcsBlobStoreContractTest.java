package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracttests.BlobStoreContractTest;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.google.cloud.storage.Blob;
import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageException;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link GcsBlobStore}.
 *
 * <p>Extends {@link BlobStoreContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link GcsBlobStore} so all inherited contract
 * methods execute without real GCS credentials or network.
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension} so that stubs set up unconditionally in
 * {@link #store()} are not flagged as unnecessary by strict stubbing when
 * some tests (e.g. {@code nullArgumentsRejected}) exercise only the SUT's
 * argument validation and never touch the mocked client.
 *
 * <p>Sprint-15 deliverable (T15.4, issue #78).
 */
class GcsBlobStoreContractTest extends BlobStoreContractTest {

    private static final String BUCKET = "contract-bucket";
    private static final String KNOWN_OBJECT = "contract/known-object.txt";
    private static final String MISSING_OBJECT = "contract/missing-object.txt";

    /** Full gs:// URI for the pre-populated object. */
    private static final String KNOWN_URI = "gs://" + BUCKET + "/" + KNOWN_OBJECT;

    /** Full gs:// URI that resolves to nothing. */
    private static final String MISSING_URI = "gs://" + BUCKET + "/" + MISSING_OBJECT;

    @Override
    protected BlobStore store() {
        Storage storage = mock(Storage.class);

        // Known blob — returns a real-ish Blob whose getContent() yields "hello".
        Blob knownBlob = mock(Blob.class);
        when(knownBlob.getContent()).thenReturn("hello".getBytes());
        when(storage.get(BlobId.of(BUCKET, KNOWN_OBJECT))).thenReturn(knownBlob);

        // Missing blob — client returns null (GcsBlobStore maps this to UncheckedIOException).
        when(storage.get(BlobId.of(BUCKET, MISSING_OBJECT))).thenReturn(null);

        // delete(missingUri): Storage.delete returns false for absent objects;
        // the adapter does NOT throw. No separate StorageException stub needed
        // because a fresh mock returns false by default for boolean returns.

        // delete(missingUri) via StorageException(404): simulate the alternative
        // 404-exception path. GcsBlobStore.delete swallows 404 StorageExceptions.
        when(storage.delete(BlobId.of(BUCKET, MISSING_OBJECT)))
                .thenThrow(new StorageException(404, "not found"));

        return new GcsBlobStore(storage);
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
