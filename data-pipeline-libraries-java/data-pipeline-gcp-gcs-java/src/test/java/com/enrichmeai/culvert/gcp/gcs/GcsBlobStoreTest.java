package com.enrichmeai.culvert.gcp.gcs;

import com.google.api.gax.paging.Page;
import com.google.cloud.storage.Blob;
import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.BlobInfo;
import com.google.cloud.storage.CopyWriter;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.UncheckedIOException;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link GcsBlobStore}. Mocks
 * {@link com.google.cloud.storage.Storage} so no real GCS credentials or
 * network are required.
 */
@ExtendWith(MockitoExtension.class)
class GcsBlobStoreTest {

    private static final String BUCKET = "my-bucket";
    private static final String OBJECT = "path/to/object.txt";
    private static final String URI = "gs://" + BUCKET + "/" + OBJECT;

    @Mock
    private Storage storage;

    @Test
    void getReturnsBlobContent() {
        Blob blob = org.mockito.Mockito.mock(Blob.class);
        byte[] payload = "hello world".getBytes();
        when(blob.getContent()).thenReturn(payload);
        when(storage.get(BlobId.of(BUCKET, OBJECT))).thenReturn(blob);

        GcsBlobStore store = new GcsBlobStore(storage);

        assertThat(store.get(URI)).isEqualTo(payload);
    }

    @Test
    void getThrowsWhenObjectMissing() {
        when(storage.get(BlobId.of(BUCKET, OBJECT))).thenReturn(null);

        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.get(URI))
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(java.io.FileNotFoundException.class)
                .hasMessageContaining(URI);
    }

    @Test
    void putWritesBlobBytes() {
        GcsBlobStore store = new GcsBlobStore(storage);

        byte[] payload = "payload".getBytes();
        store.put(URI, payload);

        ArgumentCaptor<BlobInfo> infoCaptor = ArgumentCaptor.forClass(BlobInfo.class);
        ArgumentCaptor<byte[]> bytesCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(storage).create(infoCaptor.capture(), bytesCaptor.capture());

        BlobInfo info = infoCaptor.getValue();
        assertThat(info.getBucket()).isEqualTo(BUCKET);
        assertThat(info.getName()).isEqualTo(OBJECT);
        assertThat(bytesCaptor.getValue()).isEqualTo(payload);
    }

    @Test
    void listWithPrefixYieldsAbsoluteUris() {
        Blob a = org.mockito.Mockito.mock(Blob.class);
        when(a.getName()).thenReturn("dir/a.txt");
        Blob b = org.mockito.Mockito.mock(Blob.class);
        when(b.getName()).thenReturn("dir/b.txt");

        @SuppressWarnings("unchecked")
        Page<Blob> page = (Page<Blob>) org.mockito.Mockito.mock(Page.class);
        when(page.iterateAll()).thenReturn(List.of(a, b));

        // Varargs + Mockito matchers: use any() (untyped) for the varargs
        // slot. With a typed any(Storage.BlobListOption.class), Mockito's
        // varargs handling can be brittle across versions.
        when(storage.list(eq(BUCKET), org.mockito.ArgumentMatchers.<Storage.BlobListOption>any()))
                .thenReturn(page);

        GcsBlobStore store = new GcsBlobStore(storage);

        Iterator<String> it = store.list("gs://" + BUCKET + "/dir/");
        assertThat(it.next()).isEqualTo("gs://" + BUCKET + "/dir/a.txt");
        assertThat(it.next()).isEqualTo("gs://" + BUCKET + "/dir/b.txt");
        assertThat(it.hasNext()).isFalse();
    }

    @Test
    void listWithBucketOnlyListsWholeBucket() {
        Blob a = org.mockito.Mockito.mock(Blob.class);
        when(a.getName()).thenReturn("root.txt");

        @SuppressWarnings("unchecked")
        Page<Blob> page = (Page<Blob>) org.mockito.Mockito.mock(Page.class);
        when(page.iterateAll()).thenReturn(List.of(a));

        when(storage.list(eq(BUCKET))).thenReturn(page);

        GcsBlobStore store = new GcsBlobStore(storage);

        Iterator<String> it = store.list("gs://" + BUCKET);
        assertThat(it.next()).isEqualTo("gs://" + BUCKET + "/root.txt");
        assertThat(it.hasNext()).isFalse();
    }

    @Test
    void existsReturnsTrueWhenBlobPresent() {
        Blob blob = org.mockito.Mockito.mock(Blob.class);
        when(storage.get(BlobId.of(BUCKET, OBJECT))).thenReturn(blob);

        GcsBlobStore store = new GcsBlobStore(storage);

        assertThat(store.exists(URI)).isTrue();
    }

    @Test
    void existsReturnsFalseWhenBlobAbsent() {
        when(storage.get(BlobId.of(BUCKET, OBJECT))).thenReturn(null);

        GcsBlobStore store = new GcsBlobStore(storage);

        assertThat(store.exists(URI)).isFalse();
    }

    @Test
    void deleteIsIdempotentWhenObjectMissing() {
        // Storage#delete returns false if the object did not exist; the
        // contract requires delete to be idempotent. No exception expected.
        when(storage.delete(any(BlobId.class))).thenReturn(false);

        GcsBlobStore store = new GcsBlobStore(storage);

        store.delete(URI);

        verify(storage).delete(BlobId.of(BUCKET, OBJECT));
    }

    @Test
    void deleteSwallows404StorageException() {
        when(storage.delete(any(BlobId.class)))
                .thenThrow(new StorageException(404, "not found"));

        GcsBlobStore store = new GcsBlobStore(storage);

        // Should NOT propagate the 404.
        store.delete(URI);
    }

    @Test
    void deletePropagatesNon404StorageException() {
        when(storage.delete(any(BlobId.class)))
                .thenThrow(new StorageException(500, "boom"));

        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.delete(URI))
                .isInstanceOf(StorageException.class);
    }

    @Test
    void copyWithinBucketIssuesCopyRequest() {
        CopyWriter copyWriter = org.mockito.Mockito.mock(CopyWriter.class);
        when(storage.copy(any(Storage.CopyRequest.class))).thenReturn(copyWriter);

        GcsBlobStore store = new GcsBlobStore(storage);

        String dstUri = "gs://" + BUCKET + "/path/to/copy.txt";
        store.copy(URI, dstUri);

        ArgumentCaptor<Storage.CopyRequest> req = ArgumentCaptor.forClass(Storage.CopyRequest.class);
        verify(storage).copy(req.capture());
        verify(copyWriter).getResult();

        Storage.CopyRequest captured = req.getValue();
        assertThat(captured.getSource()).isEqualTo(BlobId.of(BUCKET, OBJECT));
        assertThat(captured.getTarget().getBucket()).isEqualTo(BUCKET);
        assertThat(captured.getTarget().getName()).isEqualTo("path/to/copy.txt");
    }

    @Test
    void copyRejectsForeignSchemeSource() {
        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.copy("s3://other/foo", URI))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void copyRejectsForeignSchemeDestination() {
        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.copy(URI, "s3://other/foo"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void getRejectsNonGsUri() {
        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.get("s3://bucket/object"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("gs://");
    }

    @Test
    void putRejectsUriWithoutObjectName() {
        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.put("gs://" + BUCKET, "data".getBytes()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("object name");
    }

    @Test
    void parseRejectsUriWithoutBucket() {
        GcsBlobStore store = new GcsBlobStore(storage);

        assertThatThrownBy(() -> store.get("gs:///object-no-bucket"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bucket");
    }

    @Test
    void closeDelegatesToClient() throws Exception {
        GcsBlobStore store = new GcsBlobStore(storage);
        store.close();
        verify(storage).close();
    }
}
