package com.enrichmeai.culvert.aws.secrets;

import com.enrichmeai.culvert.contracts.SecretProvider;
import com.enrichmeai.culvert.contracttests.SecretProviderContractTest;
import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueRequest;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueResponse;
import software.amazon.awssdk.services.secretsmanager.model.ResourceNotFoundException;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link AwsSecretsManagerProvider}.
 *
 * <p>Extends {@link SecretProviderContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link AwsSecretsManagerProvider} so all inherited
 * contract methods execute without real AWS credentials or network.
 *
 * <p>The base specifies:
 * <ul>
 *   <li>{@code get("known-secret", "latest")} -&gt; {@code "the-secret-value"}</li>
 *   <li>{@code get("missing-secret", "latest")} -&gt;
 *       {@link java.util.NoSuchElementException}</li>
 *   <li>{@code get(null, "latest")} -&gt; {@code NullPointerException} or
 *       {@code IllegalArgumentException}</li>
 * </ul>
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension}, mirroring
 * {@code GcpSecretManagerContractTest}: stubs set up unconditionally in
 * {@link #provider()} would otherwise be flagged as unnecessary by strict
 * stubbing on the {@code nullNameRejected} test, which never touches the
 * mocked client.
 *
 * <p>Sprint-21 deliverable (T21.2, issue #146).
 */
class AwsSecretManagerContractTest extends SecretProviderContractTest {

    @Override
    protected SecretProvider provider() {
        SecretsManagerClient client = mock(SecretsManagerClient.class);

        // "known-secret" / AWSCURRENT -> "the-secret-value"
        GetSecretValueResponse knownResponse = GetSecretValueResponse.builder()
                .secretString("the-secret-value")
                .build();
        // "missing-secret" -> ResourceNotFoundException (AwsSecretsManagerProvider
        // maps this to NoSuchElementException, which is what the contract base
        // asserts).
        ResourceNotFoundException notFound = ResourceNotFoundException.builder()
                .message("secret not found")
                .build();

        when(client.getSecretValue(any(GetSecretValueRequest.class))).thenAnswer(inv -> {
            GetSecretValueRequest request = inv.getArgument(0);
            if ("known-secret".equals(request.secretId())) {
                return knownResponse;
            }
            throw notFound;
        });

        return new AwsSecretsManagerProvider(client);
    }
}
