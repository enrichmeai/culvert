package com.enrichmeai.culvert.gcp.secrets;

import com.enrichmeai.culvert.contracts.SecretProvider;
import com.google.api.gax.rpc.NotFoundException;
import com.google.cloud.secretmanager.v1.AccessSecretVersionResponse;
import com.google.cloud.secretmanager.v1.SecretManagerServiceClient;
import com.google.cloud.secretmanager.v1.SecretVersionName;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * {@link SecretProvider} implementation backed by Google Cloud Secret Manager.
 *
 * <p>Wraps a {@link SecretManagerServiceClient} and resolves secrets at
 * {@code projects/{projectId}/secrets/{name}/versions/{version}}.
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #SecretManagerProvider(String)} — production: builds a default
 *       {@code SecretManagerServiceClient} from Application Default
 *       Credentials.</li>
 *   <li>{@link #SecretManagerProvider(String, SecretManagerServiceClient)} —
 *       tests: inject a Mockito mock to avoid any network or credential
 *       lookup.</li>
 *   <li>{@link #SecretManagerProvider()} — no-arg constructor that reads
 *       {@code GCP_PROJECT_ID} from the environment. Required for
 *       {@link java.util.ServiceLoader} discovery via the
 *       {@code META-INF/services} registration.</li>
 * </ul>
 *
 * <h2>Environment variables</h2>
 * <ul>
 *   <li>{@code GCP_PROJECT_ID} — read by the no-arg constructor only.</li>
 * </ul>
 *
 * <p>This class is {@link AutoCloseable}; closing it closes the wrapped
 * client. Implementations never log the secret payload, even at DEBUG.
 *
 * <p>Sprint-1 deliverable for issue #5.
 */
public final class SecretManagerProvider implements SecretProvider, AutoCloseable {

    /** Environment variable read by the no-arg constructor. */
    public static final String ENV_PROJECT_ID = "GCP_PROJECT_ID";

    private final String projectId;
    private final SecretManagerServiceClient client;

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery.
     *
     * <p>Reads {@link #ENV_PROJECT_ID} from the process environment and
     * builds a default {@link SecretManagerServiceClient}.
     *
     * @throws IllegalStateException if {@code GCP_PROJECT_ID} is unset or empty.
     * @throws UncheckedIOException  if the default client cannot be created.
     */
    public SecretManagerProvider() {
        this(requireEnvProjectId());
    }

    /**
     * Production constructor — builds a default client.
     *
     * @param projectId GCP project ID. Required.
     * @throws NullPointerException  if {@code projectId} is null.
     * @throws UncheckedIOException  if the default client cannot be created.
     */
    public SecretManagerProvider(String projectId) {
        this(projectId, createDefaultClient());
    }

    /**
     * Constructor for tests and custom-credential wiring. Use this with a
     * Mockito mock of {@link SecretManagerServiceClient} to avoid touching
     * real GCP from unit tests.
     *
     * @param projectId GCP project ID. Required.
     * @param client    Pre-built client. Required. Ownership transfers to
     *                  this provider — {@link #close()} will close it.
     * @throws NullPointerException if either argument is null.
     */
    public SecretManagerProvider(String projectId, SecretManagerServiceClient client) {
        this.projectId = Objects.requireNonNull(projectId, "projectId must not be null");
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    @Override
    public String get(String name, String version) {
        Objects.requireNonNull(name, "name must not be null");
        Objects.requireNonNull(version, "version must not be null");

        SecretVersionName secretVersionName = SecretVersionName.of(projectId, name, version);
        try {
            AccessSecretVersionResponse response = client.accessSecretVersion(secretVersionName);
            return response.getPayload().getData().toStringUtf8();
        } catch (NotFoundException e) {
            // Adapt the GCP-specific exception to the contract's documented
            // NoSuchElementException. Never include the secret name in a log;
            // the message gives enough to debug without leaking secret IDs
            // into telemetry sinks downstream.
            throw new NoSuchElementException(
                    "Secret not found: projects/" + projectId + "/secrets/" + name
                            + "/versions/" + version);
        }
    }

    @Override
    public void close() {
        client.close();
    }

    private static String requireEnvProjectId() {
        String fromEnv = System.getenv(ENV_PROJECT_ID);
        if (fromEnv == null || fromEnv.isBlank()) {
            throw new IllegalStateException(
                    "Environment variable " + ENV_PROJECT_ID
                            + " is not set; required for the no-arg constructor"
                            + " (ServiceLoader discovery). Either set "
                            + ENV_PROJECT_ID + " or construct"
                            + " SecretManagerProvider(String projectId) explicitly.");
        }
        return fromEnv;
    }

    private static SecretManagerServiceClient createDefaultClient() {
        try {
            return SecretManagerServiceClient.create();
        } catch (IOException e) {
            throw new UncheckedIOException(
                    "Failed to create SecretManagerServiceClient", e);
        }
    }
}
