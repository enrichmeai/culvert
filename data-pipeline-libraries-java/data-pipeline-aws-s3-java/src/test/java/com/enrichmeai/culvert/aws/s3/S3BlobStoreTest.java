package com.enrichmeai.culvert.aws.s3;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.http.AbortableInputStream;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Response;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectResponse;
import software.amazon.awssdk.services.s3.model.S3Object;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class S3BlobStoreTest {

    @Mock
    private S3Client client;

    @Test
    void existsReturnsTrueOnHeadObjectSuccess() {
        when(client.headObject(any(HeadObjectRequest.class)))
                .thenReturn(HeadObjectResponse.builder().build());

        S3BlobStore store = new S3BlobStore(client);
        assertThat(store.exists("s3://my-bucket/path/to/file")).isTrue();
    }

    @Test
    void existsReturnsFalseOnNoSuchKey() {
        when(client.headObject(any(HeadObjectRequest.class)))
                .thenThrow(NoSuchKeyException.builder().message("not found").build());

        S3BlobStore store = new S3BlobStore(client);
        assertThat(store.exists("s3://my-bucket/missing")).isFalse();
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new S3BlobStore(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void existsRejectsNonS3Uri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.exists("gs://bucket/file"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void uriRejectsMissingBucket() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.exists("s3:///file"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void uriRejectsMissingKey() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.exists("s3://bucket"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // ---- get ----

    @Test
    void getReturnsBytesOnSuccess() {
        GetObjectResponse response = GetObjectResponse.builder().build();
        when(client.getObjectAsBytes(any(GetObjectRequest.class)))
                .thenReturn(ResponseBytes.fromByteArray(response, "hello".getBytes(StandardCharsets.UTF_8)));

        S3BlobStore store = new S3BlobStore(client);
        assertThat(store.get("s3://my-bucket/file")).isEqualTo("hello".getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void getThrowsFileNotFoundOnMissingObject() {
        when(client.getObjectAsBytes(any(GetObjectRequest.class)))
                .thenThrow(NoSuchKeyException.builder().message("not found").build());

        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.get("s3://my-bucket/missing"))
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(java.io.FileNotFoundException.class);
    }

    @Test
    void getRejectsNullUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.get(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    @Test
    void getRejectsForeignScheme() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.get("gs://bucket/file"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // ---- openInput ----

    @Test
    void openInputStreamsBytesOnSuccess() throws IOException {
        GetObjectResponse response = GetObjectResponse.builder().build();
        InputStream delegate = new ByteArrayInputStream("streamed".getBytes(StandardCharsets.UTF_8));
        when(client.getObject(any(GetObjectRequest.class)))
                .thenReturn(new ResponseInputStream<>(response, AbortableInputStream.create(delegate)));

        S3BlobStore store = new S3BlobStore(client);
        try (InputStream in = store.openInput("s3://my-bucket/file")) {
            assertThat(in.readAllBytes()).isEqualTo("streamed".getBytes(StandardCharsets.UTF_8));
        }
    }

    @Test
    void openInputThrowsFileNotFoundOnMissingObject() {
        when(client.getObject(any(GetObjectRequest.class)))
                .thenThrow(NoSuchKeyException.builder().message("not found").build());

        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.openInput("s3://my-bucket/missing"))
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(java.io.FileNotFoundException.class);
    }

    @Test
    void openInputRejectsNullUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.openInput(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    // ---- openOutput ----

    @Test
    void openOutputBuffersAndPutsOnClose() throws IOException {
        when(client.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenReturn(PutObjectResponse.builder().build());

        S3BlobStore store = new S3BlobStore(client);
        OutputStream out = store.openOutput("s3://my-bucket/streamed/file");
        out.write("payload".getBytes(StandardCharsets.UTF_8));

        // Not yet flushed to S3 before close().
        verify(client, never()).putObject(any(PutObjectRequest.class), any(RequestBody.class));

        out.close();

        ArgumentCaptor<PutObjectRequest> requestCaptor = ArgumentCaptor.forClass(PutObjectRequest.class);
        verify(client, times(1)).putObject(requestCaptor.capture(), any(RequestBody.class));
        assertThat(requestCaptor.getValue().bucket()).isEqualTo("my-bucket");
        assertThat(requestCaptor.getValue().key()).isEqualTo("streamed/file");
    }

    @Test
    void openOutputCloseIsIdempotent() throws IOException {
        when(client.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenReturn(PutObjectResponse.builder().build());

        S3BlobStore store = new S3BlobStore(client);
        OutputStream out = store.openOutput("s3://my-bucket/file");
        out.write("x".getBytes(StandardCharsets.UTF_8));
        out.close();
        out.close();

        verify(client, times(1)).putObject(any(PutObjectRequest.class), any(RequestBody.class));
    }

    @Test
    void openOutputRejectsNullUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.openOutput(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    // ---- put ----

    @Test
    void putSendsBytesToS3() {
        when(client.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenReturn(PutObjectResponse.builder().build());

        S3BlobStore store = new S3BlobStore(client);
        store.put("s3://my-bucket/file", "data".getBytes(StandardCharsets.UTF_8));

        ArgumentCaptor<PutObjectRequest> requestCaptor = ArgumentCaptor.forClass(PutObjectRequest.class);
        verify(client).putObject(requestCaptor.capture(), any(RequestBody.class));
        assertThat(requestCaptor.getValue().bucket()).isEqualTo("my-bucket");
        assertThat(requestCaptor.getValue().key()).isEqualTo("file");
    }

    @Test
    void putRejectsNullData() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.put("s3://my-bucket/file", null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void putRejectsNullUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.put(null, new byte[0]))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    // ---- list ----

    @Test
    void listYieldsAbsoluteUrisForSinglePage() {
        ListObjectsV2Response response = ListObjectsV2Response.builder()
                .contents(
                        S3Object.builder().key("dir/a.txt").build(),
                        S3Object.builder().key("dir/b.txt").build())
                .isTruncated(false)
                .build();
        when(client.listObjectsV2(any(ListObjectsV2Request.class))).thenReturn(response);

        S3BlobStore store = new S3BlobStore(client);
        Iterator<String> it = store.list("s3://my-bucket/dir/");

        assertThat(it).toIterable().containsExactly(
                "s3://my-bucket/dir/a.txt",
                "s3://my-bucket/dir/b.txt");
    }

    @Test
    void listPagesUntilNotTruncated() {
        ListObjectsV2Response page1 = ListObjectsV2Response.builder()
                .contents(S3Object.builder().key("dir/a.txt").build())
                .isTruncated(true)
                .nextContinuationToken("token-1")
                .build();
        ListObjectsV2Response page2 = ListObjectsV2Response.builder()
                .contents(S3Object.builder().key("dir/b.txt").build())
                .isTruncated(false)
                .build();
        when(client.listObjectsV2(any(ListObjectsV2Request.class)))
                .thenReturn(page1)
                .thenReturn(page2);

        S3BlobStore store = new S3BlobStore(client);
        Iterator<String> it = store.list("s3://my-bucket/dir/");

        assertThat(it).toIterable().containsExactly(
                "s3://my-bucket/dir/a.txt",
                "s3://my-bucket/dir/b.txt");
        verify(client, times(2)).listObjectsV2(any(ListObjectsV2Request.class));
    }

    @Test
    void listExhaustedIteratorThrowsNoSuchElement() {
        ListObjectsV2Response response = ListObjectsV2Response.builder()
                .isTruncated(false)
                .build();
        when(client.listObjectsV2(any(ListObjectsV2Request.class))).thenReturn(response);

        S3BlobStore store = new S3BlobStore(client);
        Iterator<String> it = store.list("s3://my-bucket/dir/");

        assertThat(it.hasNext()).isFalse();
        assertThatThrownBy(it::next).isInstanceOf(NoSuchElementException.class);
    }

    @Test
    void listRejectsNullPrefix() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.list(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    // ---- delete ----

    @Test
    void deleteInvokesDeleteObject() {
        S3BlobStore store = new S3BlobStore(client);
        store.delete("s3://my-bucket/file");

        ArgumentCaptor<DeleteObjectRequest> requestCaptor = ArgumentCaptor.forClass(DeleteObjectRequest.class);
        verify(client).deleteObject(requestCaptor.capture());
        assertThat(requestCaptor.getValue().bucket()).isEqualTo("my-bucket");
        assertThat(requestCaptor.getValue().key()).isEqualTo("file");
    }

    @Test
    void deleteMissingObjectIsIdempotent() {
        // S3's DeleteObject API itself returns 204 whether or not the key
        // existed, so the adapter issues the same call either way and must
        // not throw.
        S3BlobStore store = new S3BlobStore(client);
        store.delete("s3://my-bucket/missing");

        verify(client).deleteObject(any(DeleteObjectRequest.class));
    }

    @Test
    void deleteRejectsNullUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.delete(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }

    // ---- copy ----

    @Test
    void copyInvokesCopyObjectWithSourceAndDestination() {
        S3BlobStore store = new S3BlobStore(client);
        store.copy("s3://src-bucket/src-key", "s3://dst-bucket/dst-key");

        ArgumentCaptor<CopyObjectRequest> requestCaptor = ArgumentCaptor.forClass(CopyObjectRequest.class);
        verify(client).copyObject(requestCaptor.capture());
        CopyObjectRequest request = requestCaptor.getValue();
        assertThat(request.sourceBucket()).isEqualTo("src-bucket");
        assertThat(request.sourceKey()).isEqualTo("src-key");
        assertThat(request.destinationBucket()).isEqualTo("dst-bucket");
        assertThat(request.destinationKey()).isEqualTo("dst-key");
    }

    @Test
    void copyRejectsNullSourceUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.copy(null, "s3://bucket/key"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void copyRejectsNullDestinationUri() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.copy("s3://bucket/key", null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void copyRejectsForeignSourceScheme() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.copy("gs://bucket/key", "s3://bucket/key"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void copyRejectsForeignDestinationScheme() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.copy("s3://bucket/key", "gs://bucket/key"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
