package com.enrichmeai.culvert.contracts;

import java.util.Map;

/**
 * The framework's dependency-injection container.
 *
 * <p>{@code RuntimeContext} carries config, secrets, observability, lineage,
 * finops tags, and the lookup table for all registered Protocol implementations.
 * Every Source/Sink/Transform method receives a RuntimeContext.
 *
 * <p>{@code get(protocolType)} returns the registered implementation;
 * {@code register} overrides for tests or specialised runtimes. The framework's
 * bootstrap routine populates the registry via {@link java.util.ServiceLoader}
 * lookups against each installed cloud module (Stage 3 Java).
 *
 * <p>Java mirror of the Python {@code RuntimeContext} Protocol.
 *
 * <p>Sprint-12 (T12.4) added {@link #stageMetrics()} alongside the existing
 * {@link #observability()} accessor: {@code observability()} is the general-purpose
 * primitive surface (arbitrary name + tags), while {@code stageMetrics()} exposes
 * the typed, Culvert-specific seam that emits exactly the three standard Culvert
 * metrics ({@code rows_processed}, {@code stage_latency_ms}, {@code error_count})
 * with the fixed label schema. Both are advisory; each falls back to a no-op default.
 */
public interface RuntimeContext {

    /** The run identifier. Threaded through audit, lineage, and finops emissions. */
    String runId();

    /** The deployment environment ({@code "dev"}, {@code "staging"}, {@code "prod"}). */
    String environment();

    /** Read-only application configuration. */
    Map<String, Object> config();

    /** The registered {@link SecretProvider}. */
    SecretProvider secrets();

    /** The registered {@link ObservabilityHook}. */
    ObservabilityHook observability();

    /**
     * The registered {@link StageMetricsHook}.
     *
     * <p>Advisory: falls back to a no-op default if no real hook is registered.
     * Use this for emitting the three standard Culvert per-stage metrics
     * ({@code rows_processed}, {@code stage_latency_ms}, {@code error_count})
     * with the typed label schema. For general-purpose metrics / tracing, use
     * {@link #observability()}.
     *
     * <p>Sprint-12 / T12.4 addition.
     */
    StageMetricsHook stageMetrics();

    /** The registered {@link LineageEmitter}. */
    LineageEmitter lineage();

    /** The registered {@link FinOpsSink}. */
    FinOpsSink finops();

    /** The registered {@link GovernancePolicy}. */
    GovernancePolicy governance();

    /**
     * Look up the registered implementation of a Protocol.
     *
     * @param protocolType The interface class object.
     * @param <T>          The protocol type.
     * @return The registered implementation.
     * @throws IllegalStateException if no implementation is registered.
     */
    <T> T get(Class<T> protocolType);

    /**
     * Register a concrete implementation against a Protocol type.
     *
     * <p>Later registrations override earlier ones. Auto-config callables
     * from cloud modules register here at bootstrap time.
     *
     * @param protocolType The interface class object.
     * @param impl         The implementation to register.
     * @param <T>          The protocol type.
     */
    <T> void register(Class<T> protocolType, T impl);
}
