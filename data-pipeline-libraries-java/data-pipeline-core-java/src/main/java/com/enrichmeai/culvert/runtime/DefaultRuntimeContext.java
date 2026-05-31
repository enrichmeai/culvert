package com.enrichmeai.culvert.runtime;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.SecretProvider;

import java.io.Serializable;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Cloud-neutral concrete {@link RuntimeContext}: the framework's default
 * dependency-injection container.
 *
 * <p>Holds a {@code runId}, an {@code environment}, an immutable {@code config}
 * map, and a {@link ConcurrentHashMap} registry keyed by protocol interface
 * class. {@link #get(Class)} reads the registry; {@link #register(Class, Object)}
 * overrides an entry (last write wins). The convenience accessors
 * ({@link #secrets()}, {@link #observability()}, etc.) are thin wrappers over
 * the registry for the five well-known cross-cutting protocols.
 *
 * <h2>Defaulting policy</h2>
 *
 * <p>The accessors split into two groups:
 *
 * <ul>
 *   <li><strong>Advisory protocols</strong> — {@link #observability()},
 *       {@link #lineage()}, {@link #finops()}, {@link #governance()} — fall
 *       back to a silent {@linkplain NoOpDefaults no-op} when nothing is
 *       registered, so a minimal context is usable out of the box. A pipeline
 *       runs correctly whether or not these emit anywhere.</li>
 *   <li><strong>Hard dependencies</strong> — {@link #secrets()} (and any
 *       arbitrary protocol fetched via {@link #get(Class)}) — throw
 *       {@link IllegalStateException} when absent. Silently returning a fake
 *       secret would mask a misconfiguration as a data bug far from its cause.</li>
 * </ul>
 *
 * <h2>Construction</h2>
 *
 * <p>Use {@link #builder(String, String)} for explicit wiring (tests,
 * specialised runtimes) or {@link #fromAutoConfig(String, String, Map, AutoConfig)}
 * to pre-populate the registry from a Sprint-4 {@link AutoConfig} discovery
 * (the first discovered impl of each protocol is registered).
 *
 * <h2>Serialization (T10.6: serializable context boundary)</h2>
 *
 * <p>This class is {@link Serializable} because the GCP Dataflow adapter
 * captures a {@code RuntimeContext} inside Beam {@code DoFn}s, which Beam
 * serializes to its workers. <strong>Only the identity and config cross that
 * boundary</strong> — {@code runId}, {@code environment}, and the {@code config}
 * map. The {@linkplain #registry registry of protocol impls is {@code transient}}
 * and is <em>not</em> shipped: a worker rebuilds it lazily on first access (see
 * {@link #registry()}) from {@link AutoConfig#discover() classpath discovery}.
 *
 * <p>The consequence callers must understand: an impl placed via
 * {@link #register(Class, Object)} (or seeded by
 * {@link #fromAutoConfig fromAutoConfig}) is <strong>driver-side only</strong>.
 * It does not survive serialization to a worker; worker-side resolution is via
 * {@link java.util.ServiceLoader}/{@link AutoConfig} only. This is deliberate:
 * many adapters wrap non-serializable cloud SDK handles (e.g.
 * {@code com.google.cloud.storage.Storage}), so shipping the registry would
 * fail serialization the moment any such adapter were registered. Rebuilding
 * worker-side keeps {@code config} values the only thing required to be
 * serializable.
 *
 * <p>Cloud-neutral by construction: depends only on the contracts, the
 * auto-config registry, and {@code java.util}. No Beam, no GCP.
 *
 * <p>Sprint-9 deliverable (T9.1); serialization boundary hardened in
 * Sprint-10 (T10.6).
 */
public final class DefaultRuntimeContext implements RuntimeContext, Serializable {

    // Intentionally kept at 1L: making `registry` transient (T10.6) is a
    // serialization-compatible change — a transient field is simply absent
    // from the stream, and an old stream that carried it discards the extra.
    // There are no persisted streams (Beam ships these at runtime only), so
    // there is nothing to migrate. Do not bump.
    private static final long serialVersionUID = 1L;

    private final String runId;
    private final String environment;
    /**
     * Read-only config. The declared {@code Map<String, Object>} value type
     * can't be proven {@code Serializable} at compile time; the map is built
     * via {@link Map#copyOf} (a serializable immutable map) and callers are
     * expected to supply serializable values. This — with {@link #runId} and
     * {@link #environment} — is the <em>only</em> state that crosses the
     * serialization boundary.
     */
    @SuppressWarnings("serial")
    private final Map<String, Object> config;
    /**
     * Keyed by protocol interface class; values are protocol impls.
     *
     * <p><strong>Transient by design (T10.6).</strong> Protocol impls routinely
     * wrap non-serializable cloud SDK handles, so the registry is not shipped to
     * Beam workers. After deserialization this field is {@code null}; the first
     * access via {@link #registry()} rebuilds it from {@link AutoConfig#discover()}.
     * {@code volatile} so that double-checked lazy initialization in
     * {@link #registry()} is correct under the JMM.
     */
    private transient volatile ConcurrentHashMap<Class<?>, Object> registry;

    private DefaultRuntimeContext(Builder builder) {
        this.runId = Objects.requireNonNull(builder.runId, "runId must not be null");
        this.environment = Objects.requireNonNull(builder.environment, "environment must not be null");
        this.config = Map.copyOf(builder.config);
        this.registry = new ConcurrentHashMap<>(builder.registry);
    }

    /**
     * The protocol registry, rebuilt lazily worker-side after deserialization.
     *
     * <p>On the driver the field is populated by the constructor and this simply
     * returns it. After Beam deserializes the context onto a worker the field is
     * {@code null} (it is {@code transient}); the first call here rebuilds an
     * empty registry and repopulates it from {@link AutoConfig#discover()} —
     * i.e. from {@link java.util.ServiceLoader} entries on the worker classpath.
     * Driver-side {@link #register(Class, Object)} entries are intentionally
     * absent worker-side (see the class-level Serialization section).
     */
    private ConcurrentHashMap<Class<?>, Object> registry() {
        ConcurrentHashMap<Class<?>, Object> local = registry;
        if (local == null) {
            synchronized (this) {
                local = registry;
                if (local == null) {
                    // Build a throwaway context purely to reuse fromAutoConfig's
                    // registration wiring, then copy its (already-populated, via
                    // the constructor) registry. Reading the field directly here
                    // avoids re-entering registry() on the throwaway instance.
                    ConcurrentHashMap<Class<?>, Object> rebuilt = new ConcurrentHashMap<>(
                            fromAutoConfig(runId, environment, config, AutoConfig.discover()).registry);
                    // Publish the fully-populated map as the last step.
                    registry = rebuilt;
                    local = rebuilt;
                }
            }
        }
        return local;
    }

    /**
     * Start building a context with the required identity fields.
     *
     * @param runId       The run identifier. Required, non-blank.
     * @param environment The deployment environment. Required, non-blank.
     */
    public static Builder builder(String runId, String environment) {
        return new Builder(runId, environment);
    }

    /**
     * Build a context pre-populated from an {@link AutoConfig} discovery.
     *
     * <p>For each cross-cutting protocol that AutoConfig discovered on the
     * classpath, the <em>first</em> impl is registered. Protocols with no
     * discovered impl are simply not registered — the advisory accessors then
     * fall back to their no-op defaults and {@link #secrets()} throws on use.
     *
     * <p>Both the singular cross-cutting protocols (SecretProvider,
     * ObservabilityHook, LineageEmitter, FinOpsSink, GovernancePolicy) and the
     * list-based data protocols (Warehouse, BlobStore, JobControlRepository,
     * AuditEventPublisher, Source/Sink/Transform) are registered where present,
     * so stages can fetch them via {@link #get(Class)}.
     *
     * @param runId       The run identifier. Required, non-blank.
     * @param environment The deployment environment. Required, non-blank.
     * @param config      Read-only application configuration. Required (may be empty).
     * @param autoConfig  A discovered {@link AutoConfig}. Required.
     */
    public static DefaultRuntimeContext fromAutoConfig(String runId,
                                                       String environment,
                                                       Map<String, Object> config,
                                                       AutoConfig autoConfig) {
        Objects.requireNonNull(config, "config must not be null");
        Objects.requireNonNull(autoConfig, "autoConfig must not be null");
        Builder builder = new Builder(runId, environment).config(config);

        // Singular cross-cutting protocols: register the first discovered impl.
        autoConfig.secretProvider().ifPresent(
                impl -> builder.register(SecretProvider.class, impl));
        autoConfig.observabilityHook().ifPresent(
                impl -> builder.register(ObservabilityHook.class, impl));
        autoConfig.lineageEmitter().ifPresent(
                impl -> builder.register(LineageEmitter.class, impl));
        autoConfig.finOpsSink().ifPresent(
                impl -> builder.register(FinOpsSink.class, impl));
        autoConfig.governancePolicy().ifPresent(
                impl -> builder.register(GovernancePolicy.class, impl));

        // List-based data protocols: register the first of each present.
        registerFirst(builder, com.enrichmeai.culvert.contracts.Warehouse.class,
                autoConfig.warehouses());
        registerFirst(builder, com.enrichmeai.culvert.contracts.BlobStore.class,
                autoConfig.blobStores());
        registerFirst(builder, com.enrichmeai.culvert.contracts.JobControlRepository.class,
                autoConfig.jobControls());
        registerFirst(builder, com.enrichmeai.culvert.contracts.AuditEventPublisher.class,
                autoConfig.auditEventPublishers());

        return builder.build();
    }

    private static <T> void registerFirst(Builder builder, Class<T> type, java.util.List<? extends T> impls) {
        if (impls != null && !impls.isEmpty()) {
            builder.register(type, impls.get(0));
        }
    }

    @Override
    public String runId() {
        return runId;
    }

    @Override
    public String environment() {
        return environment;
    }

    @Override
    public Map<String, Object> config() {
        return config;
    }

    @Override
    public SecretProvider secrets() {
        Object impl = registry().get(SecretProvider.class);
        if (impl == null) {
            throw new IllegalStateException(
                    "No SecretProvider registered; install a SecretProvider adapter "
                            + "or call register(SecretProvider.class, ...). There is no "
                            + "no-op default for secrets by design.");
        }
        return (SecretProvider) impl;
    }

    @Override
    public ObservabilityHook observability() {
        return (ObservabilityHook) registry().computeIfAbsent(
                ObservabilityHook.class, k -> new NoOpDefaults.NoOpObservabilityHook());
    }

    @Override
    public LineageEmitter lineage() {
        return (LineageEmitter) registry().computeIfAbsent(
                LineageEmitter.class, k -> new NoOpDefaults.NoOpLineageEmitter());
    }

    @Override
    public FinOpsSink finops() {
        return (FinOpsSink) registry().computeIfAbsent(
                FinOpsSink.class, k -> new NoOpDefaults.NoOpFinOpsSink());
    }

    @Override
    public GovernancePolicy governance() {
        return (GovernancePolicy) registry().computeIfAbsent(
                GovernancePolicy.class, k -> new NoOpDefaults.NoOpGovernancePolicy());
    }

    @Override
    public <T> T get(Class<T> protocolType) {
        Objects.requireNonNull(protocolType, "protocolType must not be null");
        Object impl = registry().get(protocolType);
        if (impl == null) {
            throw new IllegalStateException(
                    "No implementation registered for " + protocolType.getName()
                            + "; call register(" + protocolType.getSimpleName()
                            + ".class, ...) or supply one via AutoConfig.");
        }
        return protocolType.cast(impl);
    }

    @Override
    public <T> void register(Class<T> protocolType, T impl) {
        Objects.requireNonNull(protocolType, "protocolType must not be null");
        Objects.requireNonNull(impl, "impl must not be null");
        registry().put(protocolType, impl);
    }

    /** Fluent builder for {@link DefaultRuntimeContext}. */
    public static final class Builder {

        private final String runId;
        private final String environment;
        private Map<String, Object> config = Map.of();
        private final ConcurrentHashMap<Class<?>, Object> registry = new ConcurrentHashMap<>();

        private Builder(String runId, String environment) {
            Objects.requireNonNull(runId, "runId must not be null");
            Objects.requireNonNull(environment, "environment must not be null");
            if (runId.isBlank()) {
                throw new IllegalArgumentException("runId must not be blank");
            }
            if (environment.isBlank()) {
                throw new IllegalArgumentException("environment must not be blank");
            }
            this.runId = runId;
            this.environment = environment;
        }

        /** Set the read-only configuration map (defensively copied at build). */
        public Builder config(Map<String, Object> config) {
            this.config = Objects.requireNonNull(config, "config must not be null");
            return this;
        }

        /** Register a protocol impl. Later registrations override earlier ones. */
        public <T> Builder register(Class<T> protocolType, T impl) {
            Objects.requireNonNull(protocolType, "protocolType must not be null");
            Objects.requireNonNull(impl, "impl must not be null");
            this.registry.put(protocolType, impl);
            return this;
        }

        public DefaultRuntimeContext build() {
            return new DefaultRuntimeContext(this);
        }
    }
}
