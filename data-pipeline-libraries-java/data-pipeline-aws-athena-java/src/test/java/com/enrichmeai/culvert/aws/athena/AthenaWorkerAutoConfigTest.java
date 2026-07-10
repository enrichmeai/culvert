package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.contracts.Warehouse;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Modifier;
import java.util.ServiceLoader;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Worker-side auto-config reconstruction of {@link AthenaWarehouse}, and the
 * {@code CULVERT_CLOUD} gate that keeps mixed-cloud fat jars deterministic
 * (mirror of {@code BigQueryWorkerAutoConfigTest} in the GCP family).
 */
class AthenaWorkerAutoConfigTest {

    @Test
    void exposesPublicNoArgConstructor() throws Exception {
        assertThat(Modifier.isPublic(
                AthenaWarehouse.class.getDeclaredConstructor().getModifiers())).isTrue();
    }

    @Test
    void serviceLoaderDiscoversAthenaWarehouseWithoutInstantiating() {
        boolean found = ServiceLoader.load(Warehouse.class).stream()
                .anyMatch(p -> p.type().equals(AthenaWarehouse.class));
        assertThat(found).isTrue();
    }

    @Test
    void noArgConstructionIsGatedToAwsSelector() {
        // No selector -> must throw (a GCP run's worker must never build this).
        System.clearProperty("culvert.cloud");
        assertThatThrownBy(AthenaWarehouse::new)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_CLOUD");
    }

    @Test
    void noArgConstructionRequiresDatabaseAndOutputLocation() {
        System.setProperty("culvert.cloud", "aws");
        try {
            // Gate passes, but the required Athena config is absent -> fail fast
            // with the missing key named (not a silent misconfiguration).
            assertThatThrownBy(AthenaWarehouse::new)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("ATHENA_DATABASE");
        } finally {
            System.clearProperty("culvert.cloud");
        }
    }
}
