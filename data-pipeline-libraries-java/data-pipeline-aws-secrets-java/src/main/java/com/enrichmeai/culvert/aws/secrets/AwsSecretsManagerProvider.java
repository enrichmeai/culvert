package com.enrichmeai.culvert.aws.secrets;

import com.enrichmeai.culvert.contracts.SecretProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueRequest;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueResponse;
import software.amazon.awssdk.services.secretsmanager.model.ResourceNotFoundException;

import java.util.NoSuchElementException;
import java.util.Objects;

/**
 * {@link SecretProvider} implementation backed by AWS Secrets Manager.
 *
 * <p>Wraps a {@link SecretsManagerClient} and resolves secrets by name via
 * {@code GetSecretValue}.
 *
 * <h2>The {@code "latest"} version, AWS-side</h2>
 *
 * <p>Unlike GCP Secret Manager, AWS Secrets Manager has no {@code "latest"}
 * version alias. AWS instead has <em>version stages</em> — labels attached to
 * a version, the most important being {@code AWSCURRENT}, which always
 * points at the current value of a secret (exactly what GCP's {@code
 * "latest"} means). This provider maps the contract's {@code "latest"} onto
 * {@code AWSCURRENT}:
 *
 * <ul>
 *   <li>{@code version.equals("latest")} -&gt; request sets
 *       {@link GetSecretValueRequest.Builder#versionStage(String)} to
 *       {@code "AWSCURRENT"}.</li>
 *   <li>Any other {@code version} value -&gt; treated as a native AWS
 *       {@link GetSecretValueRequest.Builder#versionId(String)} (AWS's own
 *       opaque version identifier, not a stage label).</li>
 * </ul>
 *
 * <h2>Construction</h2>
 * <ul>
 *   <li>{@link #AwsSecretsManagerProvider(Region)} — production: builds a
 *       default {@code SecretsManagerClient} for the given region from the
 *       default AWS credential/region provider chains.</li>
 *   <li>{@link #AwsSecretsManagerProvider(SecretsManagerClient)} — tests /
 *       custom wiring: inject a Mockito mock (or a LocalStack-pointed client)
 *       to avoid any real network or credential lookup.</li>
 *   <li>{@link #AwsSecretsManagerProvider()} — no-arg constructor required
 *       for {@link java.util.ServiceLoader} discovery. Builds a default
 *       client from the SDK's default region provider chain (no env-var
 *       reads of our own, unlike the GCP adapter's {@code GCP_PROJECT_ID} —
 *       AWS's {@code getSecretValue} needs only the secret name, not a
 *       project/account qualifier, so region is purely a client-construction
 *       concern here). See {@code AutoConfig}'s javadoc: adapters without a
 *       usable no-arg constructor are silently skipped by {@code
 *       ServiceLoader} discovery today.</li>
 * </ul>
 *
 * <p>This class is {@link AutoCloseable}; closing it closes the wrapped
 * client. Implementations never log the secret payload, even at DEBUG.
 *
 * <p>Sprint-21 deliverable for issue #146 (T21.2).
 */
public final class AwsSecretsManagerProvider implements SecretProvider, AutoCloseable {

    /** The contract's version alias for "the current value of this secret". */
    private static final String LATEST_VERSION_ALIAS = "latest";

    /** AWS's version stage that always points at the current secret value. */
    private static final String AWSCURRENT_STAGE = "AWSCURRENT";

    private final SecretsManagerClient client;

    /**
     * No-arg constructor for {@link java.util.ServiceLoader} discovery.
     *
     * <p>Builds a default {@link SecretsManagerClient} from the AWS SDK's
     * default region and credential provider chains.
     */
    public AwsSecretsManagerProvider() {
        this(SecretsManagerClient.create());
    }

    /**
     * Production constructor — builds a default client for the given region.
     *
     * @param region AWS region to resolve secrets in. Required.
     * @throws NullPointerException if {@code region} is null.
     */
    public AwsSecretsManagerProvider(Region region) {
        this(SecretsManagerClient.builder()
                .region(Objects.requireNonNull(region, "region must not be null"))
                .build());
    }

    /**
     * Constructor for tests and custom-credential wiring. Use this with a
     * Mockito mock of {@link SecretsManagerClient}, or a client pointed at a
     * LocalStack endpoint, to avoid touching real AWS from unit/integration
     * tests.
     *
     * @param client Pre-built client. Required. Ownership transfers to this
     *               provider — {@link #close()} will close it.
     * @throws NullPointerException if {@code client} is null.
     */
    public AwsSecretsManagerProvider(SecretsManagerClient client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }

    @Override
    public String get(String name, String version) {
        Objects.requireNonNull(name, "name must not be null");
        Objects.requireNonNull(version, "version must not be null");

        GetSecretValueRequest.Builder requestBuilder = GetSecretValueRequest.builder()
                .secretId(name);
        if (LATEST_VERSION_ALIAS.equals(version)) {
            requestBuilder.versionStage(AWSCURRENT_STAGE);
        } else {
            requestBuilder.versionId(version);
        }

        try {
            GetSecretValueResponse response = client.getSecretValue(requestBuilder.build());
            return response.secretString();
        } catch (ResourceNotFoundException e) {
            // Adapt the AWS-specific exception to the contract's documented
            // NoSuchElementException. Never include the secret value in a
            // log or exception message; the identifier alone is enough to
            // debug without leaking payloads into telemetry sinks downstream.
            throw new NoSuchElementException("Secret not found: " + name + " (version: " + version + ")");
        }
    }

    @Override
    public void close() {
        client.close();
    }
}
