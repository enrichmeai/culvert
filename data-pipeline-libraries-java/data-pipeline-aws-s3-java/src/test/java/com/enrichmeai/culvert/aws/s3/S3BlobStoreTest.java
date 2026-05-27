package com.enrichmeai.culvert.aws.s3;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
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
    void getThrowsPost8UnsupportedOperation() {
        S3BlobStore store = new S3BlobStore(client);
        assertThatThrownBy(() -> store.get("s3://my-bucket/file"))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("sprint-8");
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
}
