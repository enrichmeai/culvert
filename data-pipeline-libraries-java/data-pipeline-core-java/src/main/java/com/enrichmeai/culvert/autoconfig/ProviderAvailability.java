package com.enrichmeai.culvert.autoconfig;

/**
 * Opt-out for a {@link java.util.ServiceLoader}-discovered provider that is on the
 * classpath but must not be selected in the current environment.
 *
 * <p>Fat jars routinely carry more than one cloud family. Before Story 1.1 the only way
 * for such a provider to decline was to throw from its no-arg constructor — and
 * {@link AutoConfig} swallowed the throw, which truncated the provider list and hid every
 * provider after it. The correct shape is to construct successfully and report
 * <em>unavailable</em>: discovery then drops the provider from the candidate set without
 * losing anything, and without an error that means nothing to an operator.
 *
 * <p>{@link AutoConfig} filters unavailable providers out <strong>before</strong> it
 * decides whether a contract is ambiguous, so a gated-out adapter never causes a spurious
 * "more than one provider" failure.
 *
 * <p>Implementing this interface is optional: a provider that does not implement it is
 * always available. Implementations must not throw from {@link #isAvailable()} — the whole
 * point of the interface is that declining is not an error. A provider that throws is
 * treated as unavailable and the throw is recorded as a {@link DiscoveryFailure}.
 *
 * <p>This is a discovery concern, not a pipeline contract: it deliberately lives in
 * {@code com.enrichmeai.culvert.autoconfig} and is <em>not</em> one of Culvert's 16
 * contract interfaces.
 */
public interface ProviderAvailability {

    /**
     * Whether this provider should be considered for selection in the current
     * environment. Defaults to {@code true}.
     *
     * @return {@code false} to decline selection without raising an error
     */
    default boolean isAvailable() {
        return true;
    }
}
