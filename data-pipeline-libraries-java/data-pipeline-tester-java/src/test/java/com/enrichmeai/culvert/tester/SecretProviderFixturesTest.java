package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.SecretProvider;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.NoSuchElementException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SecretProviderFixturesTest {

    @Test
    void staticSecretProviderReturnsValuesAndThrowsForMissingNames() {
        SecretProvider sp = SecretProviderFixtures.staticSecretProvider(
                Map.of("db.password", "hunter2", "api.key", "abc"));

        assertThat(sp.get("db.password")).isEqualTo("hunter2");
        assertThat(sp.get("api.key", "latest")).isEqualTo("abc");
        assertThat(sp.get("api.key", "5")).isEqualTo("abc"); // version ignored

        assertThatThrownBy(() -> sp.get("missing"))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("missing");
    }

    @Test
    void failingSecretProviderThrowsForEveryLookup() {
        RuntimeException boom = new RuntimeException("IAM denied");
        SecretProvider sp = SecretProviderFixtures.failingSecretProvider(boom);

        assertThatThrownBy(() -> sp.get("any.name")).isSameAs(boom);
        assertThatThrownBy(() -> sp.get("any.name", "5")).isSameAs(boom);
    }

    @Test
    void notFoundForRaisesOnlyForListedNames() {
        SecretProvider sp = SecretProviderFixtures.notFoundFor("missing.one", "missing.two");

        assertThat(sp.get("present")).isEqualTo("fixture-value-for-present");
        assertThatThrownBy(() -> sp.get("missing.one")).isInstanceOf(NoSuchElementException.class);
        assertThatThrownBy(() -> sp.get("missing.two")).isInstanceOf(NoSuchElementException.class);
    }
}
