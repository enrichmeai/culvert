package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.audit.AuditEvent;
import com.enrichmeai.culvert.audit.EventKind;
import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link AuditEventPublisher} implementation must pass.
 *
 * <p>From the {@link AuditEventPublisher} Javadoc and {@code docs/CONTRACT.md} §4:
 * <ul>
 *   <li>{@code publish} takes every event kind;</li>
 *   <li>{@code flush} blocks until buffered events are acknowledged, and is a
 *       no-op on an empty buffer;</li>
 *   <li>a failed publish is never silent. A run-level event's failure throws,
 *       and an aggregate event's failure is logged and the run goes on.</li>
 * </ul>
 *
 * <p>The event kinds, and which of them are run-level, come from {@link EventKind}
 * and {@link AuditEvent#failureIsFatal()}. Those are held to the shared
 * conformance fixtures ({@code tests/contract/fixtures/audit_events.json}:
 * {@code run_level_kinds}, {@code aggregate_kinds}) by core's
 * {@code AuditEventConformanceTest}
 * ({@code data-pipeline-core-java/src/test/java/com/enrichmeai/culvert/audit/AuditEventConformanceTest.java:98}
 * for the run-level split, {@code :114} for the required payload keys). Python
 * holds its model to the same
 * file in {@code test_audit_event_conformance.py:54}
 * ({@code test_run_level_classification_matches_the_fixtures}). So this suite
 * and the Python suite agree through that one file, without this artifact
 * shipping it.
 *
 * <p>Subclasses provide:
 * <ul>
 *   <li>{@link #publisher()}: the publisher, over a backend double that
 *       accepts writes;</li>
 *   <li>{@link #failingPublisher()}: the same implementation, over a backend
 *       double that fails every write;</li>
 *   <li>{@link #delivered()}: how many events the accepting backend has
 *       acknowledged.</li>
 * </ul>
 */
public abstract class AuditEventPublisherContractTest {

    protected abstract AuditEventPublisher publisher();

    protected abstract AuditEventPublisher failingPublisher();

    protected abstract int delivered();

    /** A valid event of {@code kind}: every payload key §4 requires is present. */
    static AuditEvent event(EventKind kind) {
        Map<String, Object> payload = new LinkedHashMap<>();
        for (String key : kind.requiredPayloadKeys()) {
            payload.put(key, "contract");
        }
        return AuditEvent.of("20260908T091400Z-7f3a", "Generic", "customers", kind,
                Instant.parse("2026-09-08T09:14:00Z"), payload);
    }

    @Test
    void everyEventKindIsPublishedAndFlushed() {
        AuditEventPublisher publisher = publisher();
        for (EventKind kind : EventKind.values()) {
            publisher.publish(event(kind));
        }
        publisher.flush();

        assertThat(delivered()).as("events acknowledged after flush").isEqualTo(EventKind.values().length);
    }

    @Test
    void flushOnAnEmptyBufferIsANoOp() {
        AuditEventPublisher publisher = publisher();
        assertThatCode(() -> {
            publisher.flush();
            publisher.flush();
        }).doesNotThrowAnyException();
        assertThat(delivered()).isZero();
    }

    @Test
    void publishAfterFlushIsStillDelivered() {
        AuditEventPublisher publisher = publisher();
        publisher.publish(event(EventKind.RUN_START));
        publisher.flush();
        publisher.publish(event(EventKind.RUN_END));
        publisher.flush();

        assertThat(delivered()).isEqualTo(2);
    }

    @Test
    void aFailedRunLevelPublishThrows() {
        for (EventKind kind : EventKind.values()) {
            if (!kind.isRunLevel()) {
                continue;
            }
            AuditEventPublisher publisher = failingPublisher();
            assertThatThrownBy(() -> {
                publisher.publish(event(kind));
                publisher.flush();
            })
                    .as("%s is the run's state: losing it must fail the run", kind)
                    .isInstanceOf(RuntimeException.class);
        }
    }

    @Test
    void aFailedAggregatePublishDoesNotStopTheRun() {
        for (EventKind kind : EventKind.values()) {
            if (kind.isRunLevel()) {
                continue;
            }
            AuditEventPublisher publisher = failingPublisher();
            assertThatCode(() -> {
                publisher.publish(event(kind));
                publisher.flush();
            })
                    .as("%s is a counter: an audit hiccup must not halt ingestion", kind)
                    .doesNotThrowAnyException();
        }
    }
}
