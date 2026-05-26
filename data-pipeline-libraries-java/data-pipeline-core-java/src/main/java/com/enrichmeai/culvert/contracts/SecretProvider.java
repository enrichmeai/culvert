package com.enrichmeai.culvert.contracts;

/**
 * Single seam for secret lookup.
 *
 * <p>Implementations call Secret Manager (GCP), AWS Secrets Manager, Azure Key
 * Vault, HashiCorp Vault, or just read from environment variables.
 *
 * <p>Existing Python-adjacent shape:
 * {@code gcp_pipeline_orchestration.hooks.secrets} provides a Secret Manager
 * hook with {@code get_secret(secret_id, project_id, version_id)}. Stage 2
 * will adapt the method names ({@code get_secret} -> {@code get}) and lift
 * the class out of the orchestration package into
 * {@code data-pipeline-gcp-secrets}.
 *
 * <p>Java mirror of the Python {@code SecretProvider} Protocol.
 */
@FunctionalInterface
public interface SecretProvider {

    /**
     * Return the secret value at {@code name}.
     *
     * <p>Implementations should never log the returned value, even at DEBUG
     * level.
     *
     * @param name    The secret identifier.
     * @param version The version to fetch (default {@code "latest"}).
     * @return The secret value.
     * @throws java.util.NoSuchElementException if the secret does not exist.
     */
    String get(String name, String version);

    /** Convenience: fetch the {@code "latest"} version. */
    default String get(String name) {
        return get(name, "latest");
    }
}
