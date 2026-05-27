package com.enrichmeai.culvert.contracttests;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Trivial smoke test that proves the abstract contract test classes
 * are loadable and reflect their expected abstract methods. Real
 * contract-test wiring lives in each cloud adapter's test sources.
 */
class SmokeTest {

    @Test
    void contractTestClassesArePublicAbstract() {
        assertThat(SecretProviderContractTest.class.isInterface()).isFalse();
        assertThat(java.lang.reflect.Modifier.isAbstract(
                SecretProviderContractTest.class.getModifiers())).isTrue();
        assertThat(java.lang.reflect.Modifier.isAbstract(
                BlobStoreContractTest.class.getModifiers())).isTrue();
        assertThat(java.lang.reflect.Modifier.isAbstract(
                WarehouseContractTest.class.getModifiers())).isTrue();
    }
}
