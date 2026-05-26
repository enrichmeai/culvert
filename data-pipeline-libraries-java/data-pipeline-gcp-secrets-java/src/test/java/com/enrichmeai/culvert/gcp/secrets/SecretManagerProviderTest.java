package com.enrichmeai.culvert.gcp.secrets;

import com.google.api.gax.rpc.NotFoundException;
import com.google.api.gax.rpc.StatusCode;
import com.google.cloud.secretmanager.v1.AccessSecretVersionResponse;
import com.google.cloud.secretmanager.v1.SecretManagerServiceClient;
import com.google.cloud.secretmanager.v1.SecretPayload;
import com.google.cloud.secretmanager.v1.SecretVersionName;
import com.google.protobuf.ByteString;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SecretManagerProvider}. Mocks the
 * {@link SecretManagerServiceClient} so no real GCP credentials or network
 * are required.
 */
@ExtendWith(MockitoExtension.class)
class SecretManagerProviderTest {

    private static final String PROJECT_ID = "my-project";
    private static final String SECRET_NAME = "db-password";

    @Mock
    private SecretManagerServiceClient client;

    @Test
    void getReturnsPayloadForLatestVersionByDefault() {
        AccessSecretVersionResponse response = AccessSecretVersionResponse.newBuilder()
                .setPayload(SecretPayload.newBuilder()
                        .setData(ByteString.copyFromUtf8("s3cret!"))
                        .build())
                .build();
        when(client.accessSecretVersion(any(SecretVersionName.class))).thenReturn(response);

        SecretManagerProvider provider = new SecretManagerProvider(PROJECT_ID, client);

        String value = provider.get(SECRET_NAME);

        assertThat(value).isEqualTo("s3cret!");

        ArgumentCaptor<SecretVersionName> nameCaptor = ArgumentCaptor.forClass(SecretVersionName.class);
        verify(client).accessSecretVersion(nameCaptor.capture());
        SecretVersionName captured = nameCaptor.getValue();
        assertThat(captured.getProject()).isEqualTo(PROJECT_ID);
        assertThat(captured.getSecret()).isEqualTo(SECRET_NAME);
        assertThat(captured.getSecretVersion()).isEqualTo("latest");
    }

    @Test
    void getRequestsExplicitVersionWhenProvided() {
        AccessSecretVersionResponse response = AccessSecretVersionResponse.newBuilder()
                .setPayload(SecretPayload.newBuilder()
                        .setData(ByteString.copyFromUtf8("v3-value"))
                        .build())
                .build();
        when(client.accessSecretVersion(any(SecretVersionName.class))).thenReturn(response);

        SecretManagerProvider provider = new SecretManagerProvider(PROJECT_ID, client);

        String value = provider.get(SECRET_NAME, "3");

        assertThat(value).isEqualTo("v3-value");

        ArgumentCaptor<SecretVersionName> nameCaptor = ArgumentCaptor.forClass(SecretVersionName.class);
        verify(client).accessSecretVersion(nameCaptor.capture());
        assertThat(nameCaptor.getValue().getSecretVersion()).isEqualTo("3");
    }

    @Test
    void getThrowsNoSuchElementWhenSecretNotFound() {
        StatusCode statusCode = org.mockito.Mockito.mock(StatusCode.class);
        NotFoundException notFound = new NotFoundException(
                "secret missing", new RuntimeException("boom"), statusCode, /* retryable */ false);
        when(client.accessSecretVersion(any(SecretVersionName.class))).thenThrow(notFound);

        SecretManagerProvider provider = new SecretManagerProvider(PROJECT_ID, client);

        assertThatThrownBy(() -> provider.get("missing-secret"))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("missing-secret")
                .hasMessageContaining(PROJECT_ID);
    }

    @Test
    void closeDelegatesToClient() {
        SecretManagerProvider provider = new SecretManagerProvider(PROJECT_ID, client);
        provider.close();
        verify(client).close();
    }
}
