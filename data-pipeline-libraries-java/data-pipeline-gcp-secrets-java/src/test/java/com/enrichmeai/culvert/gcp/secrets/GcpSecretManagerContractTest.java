package com.enrichmeai.culvert.gcp.secrets;

import com.enrichmeai.culvert.contracttests.SecretProviderContractTest;
import com.enrichmeai.culvert.contracts.SecretProvider;
import com.google.api.gax.rpc.NotFoundException;
import com.google.api.gax.rpc.StatusCode;
import com.google.cloud.secretmanager.v1.AccessSecretVersionResponse;
import com.google.cloud.secretmanager.v1.SecretManagerServiceClient;
import com.google.cloud.secretmanager.v1.SecretPayload;
import com.google.cloud.secretmanager.v1.SecretVersionName;
import com.google.protobuf.ByteString;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link SecretManagerProvider}.
 *
 * <p>Extends {@link SecretProviderContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link SecretManagerProvider} so all inherited
 * contract methods execute without real GCP credentials or network.
 *
 * <p>The base specifies:
 * <ul>
 *   <li>{@code get("known-secret", "latest")} → {@code "the-secret-value"}</li>
 *   <li>{@code get("missing-secret", "latest")} → {@link java.util.NoSuchElementException}</li>
 *   <li>{@code get(null, "latest")} → {@code NullPointerException} or
 *       {@code IllegalArgumentException}</li>
 * </ul>
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension} so that stubs set up unconditionally in
 * {@link #provider()} are not flagged as unnecessary by strict stubbing
 * when some tests (e.g. {@code nullNameRejected}) exercise only the SUT's
 * argument validation and never touch the mocked client.
 *
 * <p>Sprint-15 deliverable (T15.4, issue #78).
 */
class GcpSecretManagerContractTest extends SecretProviderContractTest {

    private static final String PROJECT_ID = "contract-project";

    @Override
    protected SecretProvider provider() {
        SecretManagerServiceClient client = mock(SecretManagerServiceClient.class);

        // "known-secret" / "latest" → "the-secret-value"
        AccessSecretVersionResponse knownResponse = AccessSecretVersionResponse.newBuilder()
                .setPayload(SecretPayload.newBuilder()
                        .setData(ByteString.copyFromUtf8("the-secret-value"))
                        .build())
                .build();
        // "missing-secret" / "latest" → NotFoundException (SecretManagerProvider maps
        // this to NoSuchElementException, which is what the contract base asserts).
        StatusCode statusCode = mock(StatusCode.class);
        NotFoundException notFound = new NotFoundException(
                "secret not found",
                new RuntimeException("NOT_FOUND"),
                statusCode,
                /* retryable */ false);

        when(client.accessSecretVersion(any(SecretVersionName.class))).thenAnswer(inv -> {
            SecretVersionName name = inv.getArgument(0);
            if ("known-secret".equals(name.getSecret())) {
                return knownResponse;
            }
            throw notFound;
        });

        return new SecretManagerProvider(PROJECT_ID, client);
    }
}
