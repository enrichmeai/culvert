package com.enrichmeai.culvert.aws.secrets;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueRequest;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueResponse;
import software.amazon.awssdk.services.secretsmanager.model.ResourceNotFoundException;

import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link AwsSecretsManagerProvider}. Mocks the
 * {@link SecretsManagerClient} so no real AWS credentials or network are
 * required.
 */
@ExtendWith(MockitoExtension.class)
class AwsSecretsManagerProviderTest {

    private static final String SECRET_NAME = "db-password";

    @Mock
    private SecretsManagerClient client;

    @Test
    void getReturnsPayloadForLatestVersionByDefault() {
        GetSecretValueResponse response = GetSecretValueResponse.builder()
                .secretString("s3cret!")
                .build();
        when(client.getSecretValue(any(GetSecretValueRequest.class))).thenReturn(response);

        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);

        String value = provider.get(SECRET_NAME);

        assertThat(value).isEqualTo("s3cret!");

        ArgumentCaptor<GetSecretValueRequest> requestCaptor =
                ArgumentCaptor.forClass(GetSecretValueRequest.class);
        verify(client).getSecretValue(requestCaptor.capture());
        GetSecretValueRequest captured = requestCaptor.getValue();
        assertThat(captured.secretId()).isEqualTo(SECRET_NAME);
        // "latest" maps to the AWSCURRENT version stage, not a versionId —
        // AWS has no "latest" concept of its own.
        assertThat(captured.versionStage()).isEqualTo("AWSCURRENT");
        assertThat(captured.versionId()).isNull();
    }

    @Test
    void getRequestsExplicitVersionIdWhenProvided() {
        GetSecretValueResponse response = GetSecretValueResponse.builder()
                .secretString("v3-value")
                .build();
        when(client.getSecretValue(any(GetSecretValueRequest.class))).thenReturn(response);

        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);

        String value = provider.get(SECRET_NAME, "3");

        assertThat(value).isEqualTo("v3-value");

        ArgumentCaptor<GetSecretValueRequest> requestCaptor =
                ArgumentCaptor.forClass(GetSecretValueRequest.class);
        verify(client).getSecretValue(requestCaptor.capture());
        GetSecretValueRequest captured = requestCaptor.getValue();
        assertThat(captured.versionId()).isEqualTo("3");
        assertThat(captured.versionStage()).isNull();
    }

    @Test
    void getThrowsNoSuchElementWhenSecretNotFound() {
        ResourceNotFoundException notFound = ResourceNotFoundException.builder()
                .message("secret missing")
                .build();
        when(client.getSecretValue(any(GetSecretValueRequest.class))).thenThrow(notFound);

        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);

        assertThatThrownBy(() -> provider.get("missing-secret"))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("missing-secret");
    }

    @Test
    void getRejectsNullName() {
        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);

        assertThatThrownBy(() -> provider.get(null, "latest"))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void getRejectsNullVersion() {
        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);

        assertThatThrownBy(() -> provider.get(SECRET_NAME, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new AwsSecretsManagerProvider((SecretsManagerClient) null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void closeDelegatesToClient() {
        AwsSecretsManagerProvider provider = new AwsSecretsManagerProvider(client);
        provider.close();
        verify(client).close();
    }
}
