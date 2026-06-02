package com.enrichmeai.culvert.runtime;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.RetentionPolicy;
import com.enrichmeai.culvert.lineage.LineageEvent;

import java.io.Serializable;
import java.util.Map;
import java.util.Optional;

/**
 * Cloud-neutral no-op implementations of the framework's cross-cutting
 * protocols, used by {@link DefaultRuntimeContext} when no real adapter is
 * registered.
 *
 * <p><strong>Why no-ops exist for some protocols but not others.</strong>
 * Observability, lineage, finops, and governance are all <em>advisory</em> —
 * a pipeline can run correctly without emitting metrics, lineage events, cost
 * records, or consulting a governance catalog. So the framework supplies
 * silent no-op defaults for those four, letting a minimal {@code RuntimeContext}
 * be constructed and used out of the box.
 *
 * <p>There is deliberately <strong>no</strong> no-op {@code SecretProvider}:
 * a stage that asks for a secret has a hard data dependency, and silently
 * returning {@code null} (or an empty string) would mask a misconfiguration
 * as a runtime data bug far from its cause. {@link DefaultRuntimeContext#secrets()}
 * therefore throws {@link IllegalStateException} when no provider is registered.
 *
 * <p>Every nested impl is {@link Serializable} because a {@code RuntimeContext}
 * (and therefore the registered impls it carries) is captured by Beam
 * {@code DoFn}s in the Dataflow adapter and must survive serialization to the
 * worker. They hold no state, so serialization is trivial.
 */
final class NoOpDefaults {

    private NoOpDefaults() {
    }

    /** A {@link ObservabilityHook} that discards every metric, log, and span. */
    static final class NoOpObservabilityHook implements ObservabilityHook, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void counter(String name, long value, Map<String, String> tags) {
            // no-op
        }

        @Override
        public void gauge(String name, double value, Map<String, String> tags) {
            // no-op
        }

        @Override
        public void histogram(String name, double value, Map<String, String> tags) {
            // no-op
        }

        @Override
        public void log(String level, String message, Map<String, Object> fields) {
            // no-op
        }

        @Override
        public Span span(String name) {
            return new NoOpSpan();
        }
    }

    /** A {@link ObservabilityHook.Span} that records nothing. */
    static final class NoOpSpan implements ObservabilityHook.Span, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void setAttribute(String key, String value) {
            // no-op
        }

        @Override
        public void recordException(Throwable t) {
            // no-op
        }

        @Override
        public void close() {
            // no-op
        }
    }

    /**
     * A {@link StageMetricsHook} that discards every stage-metrics snapshot.
     *
     * <p>Used when no real metrics backend is registered (e.g. in unit tests or
     * when the GCP observability module is not on the classpath). The pipeline
     * continues normally; metrics are simply not emitted.
     *
     * <p>Sprint-12 / T12.4 addition.
     */
    static final class NoOpStageMetricsHook implements StageMetricsHook, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void recordStageMetrics(StageMetrics metrics) {
            // no-op: no metrics backend configured
        }
    }

    /** A {@link LineageEmitter} that discards every event. */
    static final class NoOpLineageEmitter implements LineageEmitter, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void emit(LineageEvent event) {
            // no-op
        }
    }

    /** A {@link FinOpsSink} that discards every cost record. */
    static final class NoOpFinOpsSink implements FinOpsSink, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void record(CostMetrics metrics, FinOpsTag tags) {
            // no-op
        }
    }

    /**
     * A {@link GovernancePolicy} with no attached policies: everything is
     * {@link DataClassification#INTERNAL}, nothing is masked, nothing has a
     * retention limit. This mirrors the contract's documented defaults.
     */
    static final class NoOpGovernancePolicy implements GovernancePolicy, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public DataClassification classify(String field, String table) {
            return DataClassification.INTERNAL;
        }

        @Override
        public Optional<MaskingPolicy> maskingFor(String field, String table) {
            return Optional.empty();
        }

        @Override
        public Optional<RetentionPolicy> retentionFor(String table) {
            return Optional.empty();
        }
    }
}
