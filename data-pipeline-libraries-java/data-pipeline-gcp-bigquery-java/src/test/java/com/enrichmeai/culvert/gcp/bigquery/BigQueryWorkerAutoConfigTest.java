package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.Warehouse;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Constructor;
import java.lang.reflect.Modifier;
import java.util.ServiceLoader;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * Worker-side auto-config reconstruction of the BigQuery adapters.
 *
 * <p>Regression guard for the bug the first real GCP deploy surfaced: a Beam
 * worker rebuilds its {@code RuntimeContext} adapter registry via
 * {@code ServiceLoader} (the driver-side registrations are {@code transient}),
 * so every config-carrying adapter MUST expose a public no-arg constructor and
 * be listed in {@code META-INF/services}. Before the fix these threw
 * {@code "No implementation registered for ...Warehouse"} on the worker while
 * every unit/emulator test passed (they injected the adapter directly).
 */
class BigQueryWorkerAutoConfigTest {

    @Test
    void bigQueryWarehouseExposesPublicNoArgConstructor() throws Exception {
        Constructor<BigQueryWarehouse> ctor = BigQueryWarehouse.class.getDeclaredConstructor();
        assertThat(Modifier.isPublic(ctor.getModifiers())).isTrue();
    }

    @Test
    void bigQueryJobControlRepositoryExposesPublicNoArgConstructor() throws Exception {
        Constructor<BigQueryJobControlRepository> ctor =
                BigQueryJobControlRepository.class.getDeclaredConstructor();
        assertThat(Modifier.isPublic(ctor.getModifiers())).isTrue();
    }

    @Test
    void serviceLoaderDiscoversWarehouseWithoutInstantiating() {
        // .stream() yields providers by class, no construction (so no client/creds).
        boolean found = ServiceLoader.load(Warehouse.class).stream()
                .anyMatch(p -> p.type().equals(BigQueryWarehouse.class));
        assertThat(found).isTrue();
    }

    @Test
    void serviceLoaderDiscoversJobControlWithoutInstantiating() {
        boolean found = ServiceLoader.load(JobControlRepository.class).stream()
                .anyMatch(p -> p.type().equals(BigQueryJobControlRepository.class));
        assertThat(found).isTrue();
    }

    @Test
    void noArgWarehouseSelfConfiguresFromProperties() {
        System.setProperty("gcp.project", "worker-test-proj");
        System.setProperty("gcp.location", "europe-west2");
        try {
            // Exercises the exact worker path: no-arg construct -> BigQueryDefaults
            // -> lazy client. getService() does not perform RPCs at construction.
            Warehouse warehouse = new BigQueryWarehouse();
            assertThat(warehouse).isInstanceOf(BigQueryWarehouse.class);
        } finally {
            System.clearProperty("gcp.project");
            System.clearProperty("gcp.location");
        }
    }

    @Test
    void bigQueryFinOpsSinkExposesPublicNoArgConstructor() throws Exception {
        // Story 1.2: this registration existed but was unconstructable, so FinOpsSink
        // was unreachable through auto-config and cost recording fell back to the no-op.
        Constructor<BigQueryFinOpsSink> ctor =
                BigQueryFinOpsSink.class.getDeclaredConstructor();
        assertThat(Modifier.isPublic(ctor.getModifiers())).isTrue();
    }

    @Test
    void serviceLoaderDiscoversFinOpsSinkWithoutInstantiating() {
        boolean found = ServiceLoader.load(FinOpsSink.class).stream()
                .anyMatch(p -> p.type().equals(BigQueryFinOpsSink.class));
        assertThat(found).isTrue();
    }

    @Test
    void noArgFinOpsSinkSelfConfiguresFromProperties() {
        System.setProperty("gcp.project", "worker-test-proj");
        System.setProperty("gcp.location", "europe-west2");
        System.setProperty("gcp.finOpsDataset", "finops_ds");
        try {
            FinOpsSink sink = new BigQueryFinOpsSink();
            assertThat(sink).isInstanceOf(BigQueryFinOpsSink.class);
        } finally {
            System.clearProperty("gcp.project");
            System.clearProperty("gcp.location");
            System.clearProperty("gcp.finOpsDataset");
        }
    }

    @Test
    void noArgFinOpsSinkFailsLoudlyWhenTheDatasetIsNotConfigured() {
        // No default is invented for FINOPS_DATASET: this repo does not agree on one.
        // The throw is now a named DiscoveryFailure (Story 1.1), not a swallowed error.
        // Env beats property in BigQueryDefaults.resolve, so this asserts nothing on a
        // machine that really has FINOPS_DATASET exported.
        assumeTrue(System.getenv("FINOPS_DATASET") == null,
                "FINOPS_DATASET is set in this environment");
        System.setProperty("gcp.project", "worker-test-proj");
        try {
            assertThatThrownBy(BigQueryFinOpsSink::new)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("FINOPS_DATASET");
        } finally {
            System.clearProperty("gcp.project");
        }
    }

    @Test
    void finOpsTableDefaultsToTheCrossLanguageConstant() {
        // Table name IS settled: "cost_metrics" on both language sides. Only the
        // dataset is left to the deployment.
        assertThat(BigQueryDefaults.finOpsTable()).isEqualTo(BigQueryFinOpsSink.DEFAULT_TABLE);
        assertThat(BigQueryFinOpsSink.DEFAULT_TABLE).isEqualTo("cost_metrics");
    }

    @Test
    void jobControlDefaultsMatchThePilot() {
        // Absent env/props, defaults are job_control / pipeline_jobs — the values
        // IngestionMain uses — so the worker rebuild lands on the same table.
        assertThat(BigQueryDefaults.jobControlDataset()).isEqualTo("job_control");
        assertThat(BigQueryDefaults.jobControlTable()).isEqualTo("pipeline_jobs");
    }
}
