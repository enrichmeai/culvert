package com.enrichmeai.culvert.azure.blob;

import com.azure.storage.blob.BlobClient;
import com.azure.storage.blob.BlobContainerClient;
import com.azure.storage.blob.BlobServiceClient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AzureBlobStoreTest {

    @Mock
    private BlobServiceClient serviceClient;

    @Mock
    private BlobContainerClient container;

    @Mock
    private BlobClient blob;

    @Test
    void existsReturnsTrueWhenBlobExists() {
        when(serviceClient.getBlobContainerClient("data")).thenReturn(container);
        when(container.getBlobClient("path/to/file")).thenReturn(blob);
        when(blob.exists()).thenReturn(Boolean.TRUE);

        AzureBlobStore store = new AzureBlobStore(serviceClient);
        assertThat(store.exists("abfs://data@myaccount.dfs.core.windows.net/path/to/file")).isTrue();
    }

    @Test
    void existsReturnsFalseWhenBlobMissing() {
        when(serviceClient.getBlobContainerClient("data")).thenReturn(container);
        when(container.getBlobClient("missing")).thenReturn(blob);
        when(blob.exists()).thenReturn(Boolean.FALSE);

        AzureBlobStore store = new AzureBlobStore(serviceClient);
        assertThat(store.exists("abfs://data@myaccount.dfs.core.windows.net/missing")).isFalse();
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new AzureBlobStore(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void existsRejectsNonAbfsUri() {
        AzureBlobStore store = new AzureBlobStore(serviceClient);
        assertThatThrownBy(() -> store.exists("s3://bucket/file"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void existsRejectsMalformedAbfsUri() {
        AzureBlobStore store = new AzureBlobStore(serviceClient);
        assertThatThrownBy(() -> store.exists("abfs://no-host-or-path"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void getThrowsPost8UnsupportedOperation() {
        AzureBlobStore store = new AzureBlobStore(serviceClient);
        assertThatThrownBy(() -> store.get("abfs://data@x.dfs.core.windows.net/file"))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("sprint-8");
    }
}
