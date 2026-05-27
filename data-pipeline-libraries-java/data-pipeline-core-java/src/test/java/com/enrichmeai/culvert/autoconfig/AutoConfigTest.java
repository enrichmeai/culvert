package com.enrichmeai.culvert.autoconfig;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Smoke tests for the auto-config registry. On the data-pipeline-core
 * classpath there are no impls, so all lookups should return empty
 * (proving the ServiceLoader path doesn't throw).
 */
class AutoConfigTest {

    @Test
    void discoverReturnsAutoConfigInstance() {
        AutoConfig config = AutoConfig.discover();
        assertThat(config).isNotNull();
    }

    @Test
    void allLookupsEmptyWithoutImpls() {
        AutoConfig config = AutoConfig.discover();
        // The data-pipeline-core test classpath has no provider entries.
        assertThat(config.warehouse()).isEmpty();
        assertThat(config.blobStore()).isEmpty();
        assertThat(config.secretProvider()).isEmpty();
        assertThat(config.jobControl()).isEmpty();
        assertThat(config.finOpsSink()).isEmpty();
        assertThat(config.observabilityHook()).isEmpty();
        assertThat(config.lineageEmitter()).isEmpty();
    }

    @Test
    void listGettersReturnEmptyListsWhenNoImpls() {
        AutoConfig config = AutoConfig.discover();
        assertThat(config.warehouses()).isEmpty();
        assertThat(config.blobStores()).isEmpty();
        assertThat(config.secretProviders()).isEmpty();
        assertThat(config.sources()).isEmpty();
        assertThat(config.sinks()).isEmpty();
        assertThat(config.transforms()).isEmpty();
        assertThat(config.pipelines()).isEmpty();
        assertThat(config.stages()).isEmpty();
    }
}
