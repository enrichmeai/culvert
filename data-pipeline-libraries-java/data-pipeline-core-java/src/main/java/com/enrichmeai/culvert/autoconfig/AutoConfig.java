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

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.ServiceConfigurationError;
import java.util.ServiceLoader;
import java.util.stream.Collectors;

/**
 * Auto-config registry.
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
 * <h2>Discovery is loud (Story 1.1)</h2>
 *
 * <p>Discovery isolates failures <strong>per provider</strong>. A provider that cannot be
 * loaded — no public no-arg constructor, a constructor that throws, a class that is not on
 * the classpath — no longer truncates the list: the remaining providers still load, and the
 * failure is recorded as a {@link DiscoveryFailure} (see {@link #failures()}) and logged at
 * WARN with the provider class and the cause. Nothing is discarded silently.
 *
 * <h2>Selection is explicit (Story 1.1)</h2>
 *
 * <p>The single-value accessors ({@link #warehouse()}, {@link #blobStore()}, …) resolve in
 * three steps:
 *
 * <ol>
 *   <li>Providers that implement {@link ProviderAvailability} and report
 *       {@code isAvailable() == false} are dropped. This runs <em>before</em> the ambiguity
 *       check, so an adapter gated out of the current environment never causes a spurious
 *       ambiguity failure.</li>
 *   <li>Exactly one remaining candidate resolves to that candidate — the common case, and
 *       unchanged from earlier releases.</li>
 *   <li>More than one remaining candidate requires an explicit selector. Without one the
 *       call fails fast with an {@link IllegalStateException} naming the candidates and the
 *       variable to set — classpath order never decides.</li>
 * </ol>
 *
 * <p>The selector for contract {@code Foo} is the environment variable
 * {@code CULVERT_FOO_PROVIDER}, falling back to the system property
 * {@code culvert.foo.provider} (the same env-then-property shape the adapters' own
 * {@code CULVERT_CLOUD} gates use). Its value is either the provider's fully-qualified
 * class name or its simple class name. A selector that matches none of the discovered
 * candidates fails fast — it never falls back to an arbitrary provider.
 */
public final class AutoConfig {

    private static final Logger LOG = LoggerFactory.getLogger(AutoConfig.class);

    /**
     * Upper bound on providers examined per contract. A guard against a pathological
     * {@link ServiceLoader} iterator that neither advances nor terminates; no real
     * classpath comes close.
     */
    private static final int MAX_PROVIDERS_PER_CONTRACT = 1000;

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
    private final List<DiscoveryFailure> failures;

    private AutoConfig(ClassLoader classLoader) {
        List<DiscoveryFailure> collected = new ArrayList<>();
        this.sources = loadServiceListRaw(Source.class, classLoader, collected);
        this.sinks = loadServiceListRaw(Sink.class, classLoader, collected);
        this.transforms = loadServiceListRaw(Transform.class, classLoader, collected);
        this.pipelines = loadServiceList(Pipeline.class, classLoader, collected);
        this.stages = loadServiceList(PipelineStage.class, classLoader, collected);
        this.runtimeContexts = loadServiceList(RuntimeContext.class, classLoader, collected);
        this.jobControl = loadServiceList(JobControlRepository.class, classLoader, collected);
        this.blobStores = loadServiceList(BlobStore.class, classLoader, collected);
        this.warehouses = loadServiceList(Warehouse.class, classLoader, collected);
        this.auditPublishers = loadServiceList(AuditEventPublisher.class, classLoader, collected);
        this.governancePolicies = loadServiceList(GovernancePolicy.class, classLoader, collected);
        this.lineageEmitters = loadServiceList(LineageEmitter.class, classLoader, collected);
        this.observabilityHooks = loadServiceList(ObservabilityHook.class, classLoader, collected);
        this.stageMetricsHooks = loadServiceList(StageMetricsHook.class, classLoader, collected);
        this.finOpsSinks = loadServiceList(FinOpsSink.class, classLoader, collected);
        this.secretProviders = loadServiceList(SecretProvider.class, classLoader, collected);
        this.failures = List.copyOf(collected);
    }

    /**
     * Discover implementations on the classpath. Each contract's
     * {@code META-INF/services} entries are loaded and instantiated via each impl's no-arg
     * constructor.
     *
     * <p>A provider that cannot be loaded does not stop the others: the failure is captured
     * in {@link #failures()} and logged at WARN. Providers that implement
     * {@link ProviderAvailability} and report themselves unavailable are excluded from the
     * discovered lists — the plural getters ({@link #blobStores()}, {@link #warehouses()}, …)
     * therefore list candidates, not every registration on the classpath.
     */
    public static AutoConfig discover() {
        return new AutoConfig(null);
    }

    /**
     * Discover implementations visible to an explicit {@link ClassLoader}, rather than the
     * thread's context class loader. Intended for tests and for hosts that isolate plugin
     * classpaths; production callers want {@link #discover()}.
     *
     * @param classLoader the loader whose {@code META-INF/services} entries to read
     */
    public static AutoConfig discover(ClassLoader classLoader) {
        return new AutoConfig(Objects.requireNonNull(classLoader, "classLoader must not be null"));
    }

    /**
     * Every provider that could not be loaded during {@link #discover()}, in discovery
     * order. Empty when discovery was clean.
     *
     * <p>These are also logged at WARN. The list exists so callers — and tests — can assert
     * on discovery health without scraping a log. Story 1.1.
     */
    public List<DiscoveryFailure> failures() {
        return failures;
    }

    public Optional<Warehouse> warehouse() {
        return select(Warehouse.class, warehouses);
    }

    public List<Warehouse> warehouses() {
        return warehouses;
    }

    public Optional<BlobStore> blobStore() {
        return select(BlobStore.class, blobStores);
    }

    public List<BlobStore> blobStores() {
        return blobStores;
    }

    public Optional<SecretProvider> secretProvider() {
        return select(SecretProvider.class, secretProviders);
    }

    public List<SecretProvider> secretProviders() {
        return secretProviders;
    }

    public Optional<JobControlRepository> jobControl() {
        return select(JobControlRepository.class, jobControl);
    }

    public List<JobControlRepository> jobControls() {
        return jobControl;
    }

    public Optional<FinOpsSink> finOpsSink() {
        return select(FinOpsSink.class, finOpsSinks);
    }

    public List<FinOpsSink> finOpsSinks() {
        return finOpsSinks;
    }

    public Optional<ObservabilityHook> observabilityHook() {
        return select(ObservabilityHook.class, observabilityHooks);
    }

    public List<ObservabilityHook> observabilityHooks() {
        return observabilityHooks;
    }

    /**
     * The {@link StageMetricsHook} discovered on the classpath, or {@link Optional#empty()}
     * if none is registered. Throws if the classpath is ambiguous and no selector is set —
     * see the class javadoc.
     */
    public Optional<StageMetricsHook> stageMetricsHook() {
        return select(StageMetricsHook.class, stageMetricsHooks);
    }

    /**
     * All {@link StageMetricsHook} impls discovered on the classpath.
     */
    public List<StageMetricsHook> stageMetricsHooks() {
        return stageMetricsHooks;
    }

    public Optional<LineageEmitter> lineageEmitter() {
        return select(LineageEmitter.class, lineageEmitters);
    }

    public List<LineageEmitter> lineageEmitters() {
        return lineageEmitters;
    }

    public Optional<AuditEventPublisher> auditEventPublisher() {
        return select(AuditEventPublisher.class, auditPublishers);
    }

    public List<AuditEventPublisher> auditEventPublishers() {
        return auditPublishers;
    }

    public Optional<GovernancePolicy> governancePolicy() {
        return select(GovernancePolicy.class, governancePolicies);
    }

    public List<GovernancePolicy> governancePolicies() {
        return governancePolicies;
    }

    public Optional<Pipeline> pipeline() {
        return select(Pipeline.class, pipelines);
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

    // --- selection ---------------------------------------------------------

    /**
     * The environment variable that selects a provider for {@code contract}, e.g.
     * {@code CULVERT_BLOBSTORE_PROVIDER} for {@code BlobStore}.
     */
    static String selectorEnvVar(Class<?> contract) {
        return "CULVERT_" + contract.getSimpleName().toUpperCase(Locale.ROOT) + "_PROVIDER";
    }

    /**
     * The system property that selects a provider for {@code contract}, e.g.
     * {@code culvert.blobstore.provider} for {@code BlobStore}. Checked after the
     * environment variable; it is the in-process hook tests use, mirroring the adapters'
     * own {@code CULVERT_CLOUD} / {@code culvert.cloud} pair.
     */
    static String selectorSystemProperty(Class<?> contract) {
        return "culvert." + contract.getSimpleName().toLowerCase(Locale.ROOT) + ".provider";
    }

    private static String selectorFor(Class<?> contract) {
        String selector = System.getenv(selectorEnvVar(contract));
        if (selector == null || selector.isBlank()) {
            selector = System.getProperty(selectorSystemProperty(contract));
        }
        return (selector == null || selector.isBlank()) ? null : selector.trim();
    }

    private static boolean matches(Object impl, String selector) {
        Class<?> type = impl.getClass();
        return type.getName().equals(selector) || type.getSimpleName().equals(selector);
    }

    /**
     * Resolve the single provider for {@code contract}. Unavailable providers have already
     * been filtered out at discovery time, so this decides only none / one / ambiguous.
     */
    private static <T> Optional<T> select(Class<T> contract, List<T> candidates) {
        String selector = selectorFor(contract);

        if (candidates.isEmpty()) {
            if (selector != null) {
                throw new IllegalStateException(
                        selectorEnvVar(contract) + " is set to '" + selector + "' but no "
                                + contract.getSimpleName()
                                + " provider was discovered on the classpath.");
            }
            return Optional.empty();
        }

        if (selector != null) {
            List<T> matched = candidates.stream()
                    .filter(impl -> matches(impl, selector))
                    .collect(Collectors.toList());
            if (matched.size() == 1) {
                return Optional.of(matched.get(0));
            }
            if (matched.isEmpty()) {
                throw new IllegalStateException(
                        selectorEnvVar(contract) + " is set to '" + selector
                                + "' but no discovered " + contract.getSimpleName()
                                + " provider matches it. Discovered: " + describe(candidates));
            }
            throw new IllegalStateException(
                    selectorEnvVar(contract) + "='" + selector + "' matches more than one "
                            + contract.getSimpleName() + " provider: " + describe(matched)
                            + ". Use the fully-qualified class name.");
        }

        if (candidates.size() == 1) {
            return Optional.of(candidates.get(0));
        }

        throw new IllegalStateException(
                "More than one " + contract.getSimpleName()
                        + " provider is available and no selector chose between them: "
                        + describe(candidates) + ". Set " + selectorEnvVar(contract)
                        + " (or the system property " + selectorSystemProperty(contract)
                        + ") to one of those class names.");
    }

    private static String describe(List<?> impls) {
        return impls.stream()
                .map(impl -> impl.getClass().getName())
                .collect(Collectors.joining(", ", "[", "]"));
    }

    // --- discovery ---------------------------------------------------------

    private static <T> List<T> loadServiceList(
            Class<T> contract, ClassLoader classLoader, List<DiscoveryFailure> failures) {
        @SuppressWarnings("unchecked")
        List<T> impls = (List<T>) loadAll(contract, classLoader, failures);
        return impls;
    }

    @SuppressWarnings("unchecked")
    private static <T> List<T> loadServiceListRaw(
            Class<?> contract, ClassLoader classLoader, List<DiscoveryFailure> failures) {
        // Generic contracts (Source<T>, Sink<T>, Transform<V, W>) erase to their raw form
        // for ServiceLoader. Same per-provider failure isolation as loadServiceList; cast
        // to the raw element type.
        return (List<T>) loadAll(contract, classLoader, failures);
    }

    /**
     * Iterate {@code contract}'s providers, isolating failures to the provider that caused
     * them and dropping providers that report themselves unavailable.
     *
     * <p>Iteration shape matters. {@link ServiceLoader}'s lookup iterator clears its pending
     * error before throwing it, so iteration resumes after a per-provider
     * {@link ServiceConfigurationError} — hence {@code continue}. Any other throwable is not
     * known to advance the iterator, so it ends iteration rather than risking a spin.
     */
    private static List<Object> loadAll(
            Class<?> contract, ClassLoader classLoader, List<DiscoveryFailure> failures) {

        ServiceLoader<?> serviceLoader;
        try {
            serviceLoader = classLoader == null
                    ? ServiceLoader.load(contract)
                    : ServiceLoader.load(contract, classLoader);
        } catch (Throwable t) {
            record(failures, contract, "<service-loader>", t);
            return List.of();
        }

        List<Object> impls = new ArrayList<>();
        Iterator<? extends ServiceLoader.Provider<?>> providers = serviceLoader.stream().iterator();
        boolean stoppedByGuard = true;

        for (int guard = 0; guard < MAX_PROVIDERS_PER_CONTRACT; guard++) {
            ServiceLoader.Provider<?> provider;
            try {
                if (!providers.hasNext()) {
                    stoppedByGuard = false;
                    break;
                }
                provider = providers.next();
            } catch (ServiceConfigurationError e) {
                // Malformed entry, missing class, or no public no-arg constructor. The
                // iterator has already moved past it, so keep going.
                record(failures, contract, describeProvider(contract, e), e);
                continue;
            } catch (Throwable t) {
                record(failures, contract, "<service-loader>", t);
                stoppedByGuard = false;
                break;
            }

            String providerName = provider.type().getName();
            Object impl;
            try {
                impl = provider.get();
            } catch (Throwable t) {
                record(failures, contract, providerName, t);
                continue;
            }

            try {
                if (impl instanceof ProviderAvailability availability && !availability.isAvailable()) {
                    LOG.debug("{} provider {} reported itself unavailable; not a candidate.",
                            contract.getSimpleName(), providerName);
                    continue;
                }
            } catch (Throwable t) {
                // isAvailable() must not throw. If it does, treat the provider as
                // unavailable and say so rather than letting one adapter break discovery.
                record(failures, contract, providerName, t);
                continue;
            }

            impls.add(impl);
        }

        if (stoppedByGuard) {
            // Exhausting the guard is itself a discovery failure. Reporting it keeps the
            // promise this class exists to make: nothing is dropped without a record.
            record(failures, contract, "<service-loader>", new IllegalStateException(
                    "Stopped after " + MAX_PROVIDERS_PER_CONTRACT + " providers for "
                            + contract.getName() + "; the remainder were not examined."));
        }

        return List.copyOf(impls);
    }

    private static void record(
            List<DiscoveryFailure> failures, Class<?> contract, String providerName, Throwable cause) {
        failures.add(new DiscoveryFailure(contract, providerName, cause));
        // The throwable is the last argument so the binding logs the whole cause chain:
        // ServiceConfigurationError wraps the real reason rather than repeating it.
        LOG.warn("Culvert auto-config could not load {} provider {}. "
                        + "Other providers for this contract are unaffected.",
                contract.getSimpleName(), providerName, cause);
    }

    /**
     * Best-effort provider name from a {@link ServiceConfigurationError} raised before the
     * provider handle existed. The JDK's messages carry the offending class name; pull the
     * first dotted token out of the message, minus the leading "{@code <service>: }".
     */
    private static String describeProvider(Class<?> contract, Throwable cause) {
        String message = cause.getMessage();
        if (message == null || message.isBlank()) {
            return "<unknown>";
        }
        String prefix = contract.getName() + ": ";
        if (message.startsWith(prefix)) {
            message = message.substring(prefix.length());
        }
        for (String token : message.split("\\s+")) {
            if (token.contains(".") && token.matches("[A-Za-z_$][A-Za-z0-9_$.]*")) {
                return token;
            }
        }
        return message;
    }
}
