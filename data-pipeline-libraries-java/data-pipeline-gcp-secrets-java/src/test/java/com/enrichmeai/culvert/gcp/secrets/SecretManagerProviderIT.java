package com.enrichmeai.culvert.gcp.secrets;

import com.google.api.gax.rpc.NotFoundException;
import com.google.api.gax.rpc.StatusCode;
import com.google.cloud.secretmanager.v1.AccessSecretVersionResponse;
import com.google.cloud.secretmanager.v1.SecretManagerServiceClient;
import com.google.cloud.secretmanager.v1.SecretPayload;
import com.google.cloud.secretmanager.v1.SecretVersionName;
import com.google.protobuf.ByteString;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;
import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Integration test for {@link SecretManagerProvider}.
 *
 * <h2>Why there is no emulator here</h2>
 * <p>Unlike BigQuery (goccy/bigquery-emulator), GCS (fsouza/fake-gcs-server),
 * and Pub/Sub (the {@code gcloud} SDK emulator wrapped by Testcontainers'
 * {@code PubSubEmulatorContainer}), Google Cloud Secret Manager ships <b>no
 * public emulator</b> — there is no container image we could start to serve the
 * Secret Manager gRPC surface offline. So this module does <b>not</b> use
 * Testcontainers and there is no {@code @Testcontainers}/{@code @Container} in
 * this class. See {@code SECRETS_IT_NOTES.md} for the full rationale.
 *
 * <h2>What this IT validates instead</h2>
 * <p>Integration is exercised in-process against a <b>stateful fake</b>
 * {@link SecretManagerServiceClient}: a Mockito mock backed by an in-memory
 * {@link Map} that behaves like a tiny Secret Manager store. The fake is wired
 * into the <b>real</b> {@link SecretManagerProvider} (via the
 * {@link SecretManagerProvider#SecretManagerProvider(String,
 * SecretManagerServiceClient) client-injecting constructor}), so the adapter's
 * production code path — building the {@link SecretVersionName}, calling
 * {@code accessSecretVersion}, decoding the UTF-8 payload, and adapting
 * {@link NotFoundException} to the contract's {@link NoSuchElementException} —
 * runs end-to-end against a store that holds real state across calls.
 *
 * <p>Where {@code SecretManagerProviderTest} stubs a single canned response per
 * test and asserts on the captured request, this IT seeds a populated store and
 * drives several contract operations against the same backing map, complementary
 * to (not a copy of) the unit test:
 * <ul>
 *   <li>multi-secret round-trip — distinct names resolve to distinct values;</li>
 *   <li>single-arg {@code get} defaults to the {@code "latest"} version;</li>
 *   <li>an explicit version is resolved against the store;</li>
 *   <li>a missing secret surfaces as {@link NoSuchElementException};</li>
 *   <li>{@link SecretManagerProvider#close()} delegates to the client.</li>
 * </ul>
 *
 * <p>Named {@code *IT.java} so failsafe picks it up under the parent's
 * {@code it} profile (and surefire ignores it under {@code mvn test}); it needs
 * no Docker daemon and no network. Sprint-10 deliverable (T10.5).
 */
class SecretManagerProviderIT {

    private static final String PROJECT_ID = "culvert-it-project";

    /**
     * In-memory fake store keyed by {@code "{secret}/{version}"}. The mocked
     * client reads from this map, so it behaves like a stateful Secret Manager
     * across repeated calls rather than a one-shot stub.
     */
    private Map<String, String> store;

    private SecretManagerServiceClient fakeClient;
    private SecretManagerProvider provider;

    /** Build the version-qualified key the fake store is indexed by. */
    private static String key(String secret, String version) {
        return secret + "/" + version;
    }

    /** Seed a secret value at an explicit version in the fake store. */
    private void seed(String secret, String version, String value) {
        store.put(key(secret, version), value);
    }

    @BeforeEach
    void setUp() {
        store = new HashMap<>();
        fakeClient = mock(SecretManagerServiceClient.class);

        // Wire the mock to read from the in-memory store. Any SecretVersionName
        // whose project/secret/version isn't present surfaces as the GCP
        // NotFoundException, exactly as the real service would, so the adapter's
        // exception-adaptation path is exercised.
        when(fakeClient.accessSecretVersion(any(SecretVersionName.class)))
                .thenAnswer(invocation -> {
                    SecretVersionName name = invocation.getArgument(0);
                    assertThat(name.getProject()).isEqualTo(PROJECT_ID);
                    String value = store.get(key(name.getSecret(), name.getSecretVersion()));
                    if (value == null) {
                        throw notFound();
                    }
                    return AccessSecretVersionResponse.newBuilder()
                            .setPayload(SecretPayload.newBuilder()
                                    .setData(ByteString.copyFromUtf8(value))
                                    .build())
                            .build();
                });

        provider = new SecretManagerProvider(PROJECT_ID, fakeClient);
    }

    @AfterEach
    void tearDown() {
        // The provider owns the client; closing it must delegate to the client.
        provider.close();
    }

    /** Mirror the unit test's NotFoundException construction (mocked StatusCode). */
    private static NotFoundException notFound() {
        StatusCode statusCode = mock(StatusCode.class);
        return new NotFoundException(
                "secret missing", new RuntimeException("boom"), statusCode, /* retryable */ false);
    }

    @Test
    void roundTripsMultipleSecretsAgainstTheSameStore() {
        // A populated store: several distinct secrets, each at "latest".
        seed("db-password", "latest", "p@ss-1");
        seed("api-key", "latest", "ak-live-42");
        seed("signing-key", "latest", "sign-xyz");

        // Each name resolves to its own value against the same backing store.
        assertThat(provider.get("db-password")).isEqualTo("p@ss-1");
        assertThat(provider.get("api-key")).isEqualTo("ak-live-42");
        assertThat(provider.get("signing-key")).isEqualTo("sign-xyz");
    }

    @Test
    void singleArgGetResolvesLatestVersion() {
        // Only "latest" is seeded; the contract's single-arg get must hit it.
        seed("rotating-token", "latest", "tok-latest");

        assertThat(provider.get("rotating-token")).isEqualTo("tok-latest");
    }

    @Test
    void explicitVersionIsResolvedDistinctlyFromLatest() {
        // Same secret, two versions with different values: the explicit version
        // request must return the pinned value, not "latest".
        seed("rotating-token", "latest", "tok-v7");
        seed("rotating-token", "3", "tok-v3");

        assertThat(provider.get("rotating-token", "3")).isEqualTo("tok-v3");
        assertThat(provider.get("rotating-token")).isEqualTo("tok-v7");
    }

    @Test
    void missingSecretSurfacesAsNoSuchElement() {
        // Nothing seeded for this name: the fake throws NotFoundException, which
        // the adapter must adapt to the contract's NoSuchElementException.
        assertThatThrownBy(() -> provider.get("absent-secret"))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("absent-secret")
                .hasMessageContaining(PROJECT_ID);
    }

    @Test
    void closeDelegatesToClient() {
        // tearDown() also closes, but close() is documented idempotent-by-
        // delegation; assert the delegation explicitly here.
        provider.close();
        verify(fakeClient).close();
    }
}
