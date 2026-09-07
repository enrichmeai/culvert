package com.enrichmeai.culvert.autoconfig;

import java.util.Objects;

/**
 * One provider that {@link AutoConfig} could not load, captured rather than discarded.
 *
 * <p>Before Story 1.1, {@code loadServiceList} wrapped the entire {@code ServiceLoader}
 * iteration in {@code catch (Throwable ignored)}: a single failing provider silently
 * truncated the list. Failures are now recorded here, one per provider, and logged at
 * WARN. They are available programmatically via {@link AutoConfig#failures()} so callers
 * (and tests) can assert on them instead of scraping a log.
 *
 * @param contract      the contract interface being discovered
 * @param providerClass the fully-qualified name of the provider that failed, or a
 *                      best-effort description when the failure happened before the
 *                      provider class could be identified
 * @param cause         the throwable raised while loading or constructing the provider
 */
public record DiscoveryFailure(Class<?> contract, String providerClass, Throwable cause) {

    public DiscoveryFailure {
        Objects.requireNonNull(contract, "contract must not be null");
        Objects.requireNonNull(providerClass, "providerClass must not be null");
        Objects.requireNonNull(cause, "cause must not be null");
    }

    /** Human-readable one-liner: {@code <Contract>: <provider> — <cause>}. */
    @Override
    public String toString() {
        return contract.getSimpleName() + ": " + providerClass + " — " + cause;
    }
}
