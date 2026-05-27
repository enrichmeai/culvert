package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.SecretProvider;
import org.junit.jupiter.api.Test;

import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link SecretProvider} implementation must pass.
 *
 * <p>Subclasses provide a {@link SecretProvider} (configured to return
 * "the-secret-value" for {@code "known-secret"} and to throw
 * {@code NoSuchElementException} for {@code "missing-secret"}).
 *
 * <p>Example wiring in a cloud-adapter module's test sources:
 *
 * <pre>{@code
 * class SecretManagerProviderContractTest extends SecretProviderContractTest {
 *     protected SecretProvider provider() {
 *         SecretManagerServiceClient client = mockClient(
 *             Map.of("known-secret", "the-secret-value"));
 *         return new SecretManagerProvider("my-project", client);
 *     }
 * }
 * }</pre>
 *
 * <p>Sprint-5 deliverable.
 */
public abstract class SecretProviderContractTest {

    /**
     * Provide the {@link SecretProvider} under test. Implementations must
     * configure it to:
     * <ul>
     *   <li>Return {@code "the-secret-value"} for
     *       {@code get("known-secret", "latest")}</li>
     *   <li>Throw {@link NoSuchElementException} for
     *       {@code get("missing-secret", "latest")}</li>
     * </ul>
     */
    protected abstract SecretProvider provider();

    @Test
    void getKnownSecretReturnsValue() {
        assertThat(provider().get("known-secret", "latest"))
                .isEqualTo("the-secret-value");
    }

    @Test
    void getMissingSecretThrowsNoSuchElement() {
        assertThatThrownBy(() -> provider().get("missing-secret", "latest"))
                .isInstanceOf(NoSuchElementException.class);
    }

    @Test
    void nullNameRejected() {
        assertThatThrownBy(() -> provider().get(null, "latest"))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
