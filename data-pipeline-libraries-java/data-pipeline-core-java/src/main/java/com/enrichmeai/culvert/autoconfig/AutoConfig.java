package com.enrichmeai.culvert.autoconfig;

import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.Pipeline;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.SecretProvider;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.contracts.Transform;
import com.enrichmeai.culvert.contracts.Warehouse;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.ServiceLoader;

/**
 * Stage 3 auto-config registry.
 *
 * <p>Discovers Culvert contract implementations on the classpath via
 * {@link ServiceLoader} and exposes typed lookup methods. Each GCP/AWS/
 * Azure adapter module pre-registers its impls under
 * {@code META-INF/services/com.enrichmeai.culvert.contracts.<Contract>}.
 *
 * <p>Usage:
 *
 * <pre>{@code
 * AutoConfig config = AutoConfig.discover();
 * Warehouse warehouse = config.warehouse()
 *     .orElseThrow(() -> new IllegalStateException("No Warehouse on classpath"));
 * }</pre>
 *
 * <p>Most adapters require constructor arguments (BigQuery client + project
 * + dataset, GCS client, etc.) that ServiceLoader can't supply. Those
 * adapters' {@code META-INF/services} entries are reserved for the future
 * config-driven discovery wave — calling {@link #warehouse()} today on a
 * classpath that contains only the sprint-1 adapters will return
 * {@link Optional#empty()} unless a no-arg-friendly impl is also present.
 *
 * <p>Sprint-4 deliverable. The full config-driven instantiation arrives
 * in sprint-5.
 */
public final class AutoConfig {

    private final List<Source<?>> sources;
    private final List<Sink<?>> sinks;
    private final List<Transform<?, ?>> transforms;
    private final List<Pipeline> pipelines;
    private final List<PipelineStage> stages;
    private final List<RuntimeContext> runtimeContexts;
    private final List<JobControlRepository> jobControl;
    private final List<BlobStore> blobStores;
    private final List<Warehouse> warehouses;
    private final List<AuditEventPublisher> auditPublishers;
    private final List<GovernancePolicy> governancePolicies;
    private final List<LineageEmitter> lineageEmitters;
    private final List<ObservabilityHook> observabilityHooks;
    private final List<StageMetricsHook> stageMetricsHooks;
    private final List<FinOpsSink> finOpsSinks;
    private final List<SecretProvider> secretProviders;

    private AutoConfig() {
        this.sources = loadServiceListRaw(Source.class);
        this.sinks = loadServiceListRaw(Sink.class);
        this.transforms = loadServiceListRaw(Transform.class);
        this.pipelines = loadServiceList(Pipeline.class);
        this.stages = loadServiceList(PipelineStage.class);
        this.runtimeContexts = loadServiceList(RuntimeContext.class);
        this.jobControl = loadServiceList(JobControlRepository.class);
        this.blobStores = loadServiceList(BlobStore.class);
        this.warehouses = loadServiceList(Warehouse.class);
        this.auditPublishers = loadServiceList(AuditEventPublisher.class);
        this.governancePolicies = loadServiceList(GovernancePolicy.class);
        this.lineageEmitters = loadServiceList(LineageEmitter.class);
        this.observabilityHooks = loadServiceList(ObservabilityHook.class);
        this.stageMetricsHooks = loadServiceList(StageMetricsHook.class);
        this.finOpsSinks = loadServiceList(FinOpsSink.class);
        this.secretProviders = loadServiceList(SecretProvider.class);
    }

    /**
     * Discover implementations on the classpath. Each contract's
     * {@code META-INF/services} entries are loaded and instantiated via
     * each impl's no-arg constructor; impls without a no-arg constructor
     * are silently skipped (sprint-4 limitation; sprint-5 adds config-
     * driven instantiation).
     */
    public static AutoConfig discover() {
        return new AutoConfig();
    }

    public Optional<Warehouse> warehouse() {
        return first(warehouses);
    }

    public List<Warehouse> warehouses() {
        return warehouses;
    }

    public Optional<BlobStore> blobStore() {
        return first(blobStores);
    }

    public List<BlobStore> blobStores() {
        return blobStores;
    }

    public Optional<SecretProvider> secretProvider() {
        return first(secretProviders);
    }

    public List<SecretProvider> secretProviders() {
        return secretProviders;
    }

    public Optional<JobControlRepository> jobControl() {
        return first(jobControl);
    }

    public List<JobControlRepository> jobControls() {
        return jobControl;
    }

    public Optional<FinOpsSink> finOpsSink() {
        return first(finOpsSinks);
    }

    public List<FinOpsSink> finOpsSinks() {
        return finOpsSinks;
    }

    public Optional<ObservabilityHook> observabilityHook() {
        return first(observabilityHooks);
    }

    public List<ObservabilityHook> observabilityHooks() {
        return observabilityHooks;
    }

    /**
     * The first {@link StageMetricsHook} discovered on the classpath, or
     * {@link Optional#empty()} if none is registered.
     *
     * <p>Sprint-12 / T12.4 addition.
     */
    public Optional<StageMetricsHook> stageMetricsHook() {
        return first(stageMetricsHooks);
    }

    /**
     * All {@link StageMetricsHook} impls discovered on the classpath.
     *
     * <p>Sprint-12 / T12.4 addition.
     */
    public List<StageMetricsHook> stageMetricsHooks() {
        return stageMetricsHooks;
    }

    public Optional<LineageEmitter> lineageEmitter() {
        return first(lineageEmitters);
    }

    public List<LineageEmitter> lineageEmitters() {
        return lineageEmitters;
    }

    public Optional<AuditEventPublisher> auditEventPublisher() {
        return first(auditPublishers);
    }

    public List<AuditEventPublisher> auditEventPublishers() {
        return auditPublishers;
    }

    public Optional<GovernancePolicy> governancePolicy() {
        return first(governancePolicies);
    }

    public List<GovernancePolicy> governancePolicies() {
        return governancePolicies;
    }

    public Optional<Pipeline> pipeline() {
        return first(pipelines);
    }

    public List<Pipeline> pipelines() {
        return pipelines;
    }

    public List<Source<?>> sources() {
        return sources;
    }

    public List<Sink<?>> sinks() {
        return sinks;
    }

    public List<Transform<?, ?>> transforms() {
        return transforms;
    }

    public List<PipelineStage> stages() {
        return stages;
    }

    public List<RuntimeContext> runtimeContexts() {
        return runtimeContexts;
    }

    // --- helpers -----------------------------------------------------------

    private static <T> List<T> loadServiceList(Class<T> contract) {
        List<T> impls = new ArrayList<>();
        try {
            for (T impl : ServiceLoader.load(contract)) {
                impls.add(impl);
            }
        } catch (Throwable ignored) {
            // ServiceConfigurationError from missing no-arg constructors:
            // sprint-4 limitation. Sprint-5 config-driven instantiation
            // will replace this swallow with structured reporting.
        }
        return List.copyOf(impls);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static <T> List<T> loadServiceListRaw(Class<?> contract) {
        // Generic contracts (Source<T>, Sink<T>, Transform<V, W>) erase to
        // their raw form for ServiceLoader. Same swallow semantics as
        // loadServiceList; cast to the raw element type.
        List<T> impls = new ArrayList<>();
        try {
            ServiceLoader<?> loader = ServiceLoader.load(contract);
            for (Object impl : loader) {
                impls.add((T) impl);
            }
        } catch (Throwable ignored) {
            // Sprint-4 limitation.
        }
        return List.copyOf(impls);
    }

    private static <T> Optional<T> first(List<T> impls) {
        return impls.isEmpty() ? Optional.empty() : Optional.of(impls.get(0));
    }
}
