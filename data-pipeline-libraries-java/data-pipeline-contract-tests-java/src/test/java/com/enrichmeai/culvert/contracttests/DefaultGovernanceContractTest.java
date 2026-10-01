package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.audit.AuditEvent;
import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.junit.jupiter.api.Nested;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * The references for the three governance-and-cost suites.
 *
 * <p>Lineage and FinOps: the framework's own no-op defaults, the ones
 * {@link DefaultRuntimeContext} hands out when nothing is registered. They
 * pass, which is the suites' statement that an implementation doing nothing
 * is legal. Audit has no no-op default (a silent audit trail is the bug its
 * contract exists to prevent), so its reference is an in-memory buffering
 * publisher that fails loudly on run-level events.
 */
class DefaultGovernanceContractTest {

    private static DefaultRuntimeContext emptyContext() {
        return DefaultRuntimeContext.builder("contract-run", "test").build();
    }

    @Nested
    class NoOpLineage extends LineageEmitterContractTest {
        @Override
        protected LineageEmitter emitter() {
            return emptyContext().lineage();
        }
    }

    @Nested
    class NoOpFinOps extends FinOpsSinkContractTest {
        @Override
        protected FinOpsSink sink() {
            return emptyContext().finops();
        }
    }

    /** Buffers until flush; a backend failure throws for run-level events only. */
    static final class InMemoryAuditPublisher implements AuditEventPublisher {
        private final List<AuditEvent> buffer = new ArrayList<>();
        private final List<AuditEvent> acknowledged;
        private final boolean backendDown;

        InMemoryAuditPublisher(List<AuditEvent> acknowledged, boolean backendDown) {
            this.acknowledged = acknowledged;
            this.backendDown = backendDown;
        }

        @Override
        public void publish(AuditEvent event) {
            buffer.add(Objects.requireNonNull(event, "event"));
        }

        @Override
        public void flush() {
            for (AuditEvent event : buffer) {
                if (backendDown) {
                    if (event.failureIsFatal()) {
                        buffer.clear();
                        throw new IllegalStateException("audit write failed for " + event.eventKind());
                    }
                    continue; // aggregate: logged and dropped, the run goes on
                }
                acknowledged.add(event);
            }
            buffer.clear();
        }
    }

    @Nested
    class InMemoryAudit extends AuditEventPublisherContractTest {
        private final List<AuditEvent> acknowledged = new ArrayList<>();

        @Override
        protected AuditEventPublisher publisher() {
            return new InMemoryAuditPublisher(acknowledged, false);
        }

        @Override
        protected AuditEventPublisher failingPublisher() {
            return new InMemoryAuditPublisher(new ArrayList<>(), true);
        }

        @Override
        protected int delivered() {
            return acknowledged.size();
        }
    }
}
