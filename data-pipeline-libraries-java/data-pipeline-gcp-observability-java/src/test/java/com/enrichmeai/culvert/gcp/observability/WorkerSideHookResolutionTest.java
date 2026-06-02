package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.google.cloud.monitoring.v3.MetricServiceClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.MockedStatic;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;

/**
 * Epic #47 gate test: proves that worker-side {@link DefaultRuntimeContext} registry
 * rebuild (the T10.6 transient-registry pattern) resolves a REAL {@link StageMetricsHook}
 * implementation when {@code data-pipeline-gcp-observability-java} is on the classpath.
 *
 * <p>Before T12.6, {@link CloudMonitoringMetricsHook} had no no-arg constructor, so
 * {@link AutoConfig#discover()} silently skipped it → the worker got a NoOp. This test
 * proves that is no longer the case: after deserialization the hook is real.
 *
 * <p>The test runs in the {@code data-pipeline-gcp-observability-java} test tree because:
 * <ul>
 *   <li>This module depends on {@code data-pipeline-core-java} (which provides
 *       {@link DefaultRuntimeContext} and {@link AutoConfig}).</li>
 *   <li>The SPI entries for {@link StageMetricsHook} and {@link ObservabilityHook}
 *       are in this module's own {@code META-INF/services} — they are therefore on the
 *       test classpath automatically without any additional wiring.</li>
 *   <li>We avoid perturbing the dataflow module's classpath, which would change what
 *       {@code AutoConfig.discover()} resolves in existing tests there.</li>
 * </ul>
 *
 * <p>T12.6 / issue #91.
 */
class WorkerSideHookResolutionTest {

    @AfterEach
    void clearProjectSystemProperty() {
        System.clearProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT);
    }

    /**
     * The epic gate: after a serialization round-trip (simulating Beam worker
     * deserialization), the worker-side registry rebuild via {@link AutoConfig#discover()}
     * resolves a REAL {@link CloudMonitoringMetricsHook}, not NoOp.
     *
     * <p>Requires: system property set + {@code MetricServiceClient.create()} mocked.
     * The mock is active during the registry rebuild (which runs synchronously on this
     * thread when {@code stageMetrics()} is first called on the deserialized context).
     */
    @Test
    void workerSideRebuildResolvesRealStageMetricsHookWhenObservabilityModuleOnClasspath()
            throws Exception {
        System.setProperty(CloudMonitoringMetricsHook.SYSPROP_GCP_PROJECT, "epic-gate-project");

        try (MockedStatic<MetricServiceClient> staticClient =
                     mockStatic(MetricServiceClient.class)) {
            staticClient.when(MetricServiceClient::create).thenReturn(mock(MetricServiceClient.class));

            // Build a driver-side context (nothing GCP-specific registered explicitly).
            DefaultRuntimeContext driverCtx = DefaultRuntimeContext
                    .builder("run-epic-gate", "prod")
                    .build();

            // Round-trip it through Java serialization — simulates Beam shipping
            // the context to a Dataflow worker. The transient registry is NOT carried.
            DefaultRuntimeContext workerCtx = roundTrip(driverCtx);

            // Identity survives.
            assertThat(workerCtx.runId()).isEqualTo("run-epic-gate");
            assertThat(workerCtx.environment()).isEqualTo("prod");

            // Worker-side rebuild: stageMetrics() triggers AutoConfig.discover() which
            // loads the SPI entry and instantiates CloudMonitoringMetricsHook via its
            // no-arg ctor. The mock for MetricServiceClient.create() is active on this
            // thread, so instantiation succeeds.
            StageMetricsHook resolved = workerCtx.stageMetrics();

            assertThat(resolved)
                    .as("Worker-side rebuild must resolve the REAL hook, not NoOp")
                    .isInstanceOf(CloudMonitoringMetricsHook.class);

            // The resolved hook must be usable (no throw from recordStageMetrics).
            assertThatCode(() -> resolved.recordStageMetrics(
                    new StageMetrics("epic-gate-pipeline", "run-epic-gate", "my-stage",
                            0L, 42.0, 0L)))
                    .doesNotThrowAnyException();
        }
    }

    /**
     * The observability hook (CloudTraceObservabilityHook) also resolves worker-side
     * via ServiceLoader — no mocking needed because GlobalOpenTelemetry.get() never throws.
     */
    @Test
    void workerSideRebuildResolvesRealObservabilityHookWhenObservabilityModuleOnClasspath()
            throws Exception {
        DefaultRuntimeContext driverCtx = DefaultRuntimeContext
                .builder("run-obs-gate", "prod")
                .build();

        DefaultRuntimeContext workerCtx = roundTrip(driverCtx);

        com.enrichmeai.culvert.contracts.ObservabilityHook resolved = workerCtx.observability();
        assertThat(resolved)
                .as("Worker-side rebuild must resolve CloudTraceObservabilityHook, not NoOp")
                .isInstanceOf(CloudTraceObservabilityHook.class);
    }

    // --- serialization helper ------------------------------------------------

    private static DefaultRuntimeContext roundTrip(DefaultRuntimeContext ctx) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(ctx);
        }
        try (ObjectInputStream in = new ObjectInputStream(
                new ByteArrayInputStream(bytes.toByteArray()))) {
            return (DefaultRuntimeContext) in.readObject();
        }
    }
}
