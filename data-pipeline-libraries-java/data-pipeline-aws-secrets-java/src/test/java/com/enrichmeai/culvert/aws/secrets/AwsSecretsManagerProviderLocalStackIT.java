package com.enrichmeai.culvert.aws.secrets;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.containers.localstack.LocalStackContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.CreateSecretRequest;

import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.SECRETSMANAGER;

/**
 * Integration tests for {@link AwsSecretsManagerProvider} against a real
 * Secrets Manager API emulator (localstack/localstack) via Testcontainers.
 *
 * <p>Where {@code AwsSecretsManagerProviderTest} mocks the client, this IT
 * creates a real secret in the running LocalStack container and exercises the
 * full {@code SecretProvider} surface end-to-end. Mirrors the style of
 * {@code S3BlobStoreLocalStackIT}. Suffixed {@code IT} so default surefire
 * skips it; runs only under {@code mvn -P it verify} (Docker required).
 *
 * <p>Sprint-21 deliverable (T21.2, issue #146) — added at architect
 * verification after the dev-agent's connection dropped pre-IT.
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AwsSecretsManagerProviderLocalStackIT {

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(DockerImageName.parse("localstack/localstack:3.4.0"))
                    .withServices(SECRETSMANAGER);

    private AwsSecretsManagerProvider provider;

    @BeforeAll
    void setUp() {
        SecretsManagerClient client = SecretsManagerClient.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(SECRETSMANAGER))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                .build();
        client.createSecret(CreateSecretRequest.builder()
                .name("culvert/it/db-password")
                .secretString("s3cr3t-value")
                .build());
        provider = new AwsSecretsManagerProvider(client);
    }

    @Test
    void getReturnsStoredSecretValue() {
        assertThat(provider.get("culvert/it/db-password")).isEqualTo("s3cr3t-value");
    }

    @Test
    void getMissingSecretThrowsNoSuchElement() {
        assertThatThrownBy(() -> provider.get("culvert/it/does-not-exist"))
                .isInstanceOf(NoSuchElementException.class);
    }

    @Test
    void getNullNameRejected() {
        assertThatThrownBy(() -> provider.get(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
