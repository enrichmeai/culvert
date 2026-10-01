package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.lineage.LineageAudit;
import com.enrichmeai.culvert.lineage.LineageDestination;
import com.enrichmeai.culvert.lineage.LineageEvent;
import com.enrichmeai.culvert.lineage.LineagePipeline;
import com.enrichmeai.culvert.lineage.LineageSource;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * Contract tests every {@link LineageEmitter} implementation must pass.
 *
 * <p>The interface says only that {@code emit} publishes a lineage event. The
 * framework's own default, {@code NoOpLineageEmitter}, discards every event,
 * and the suite treats that as legal. So the cases are: an event of either
 * shape (all four sub-records, or a pipeline alone, since every sub-record is
 * optional) is taken without an exception, and, where the binding can observe
 * its backend ({@link #delivered()}), each emitted event reaches it once.
 *
 * <p>Nothing about failure or {@code null} is tested: the interface is silent
 * on both, and the no-op default accepts anything.
 */
public abstract class LineageEmitterContractTest {

    protected abstract LineageEmitter emitter();

    /**
     * How many events the backend has received, or empty for an implementation
     * whose backend the binding cannot observe (the no-op default).
     */
    protected OptionalInt delivered() {
        return OptionalInt.empty();
    }

    static LineageEvent completeEvent() {
        Instant now = Instant.parse("2026-09-08T09:14:00Z");
        return LineageEvent.builder()
                .source(new LineageSource("gcs", "gs://bucket/landing/customers.csv",
                        Optional.empty(), Optional.of(Map.of("format", "csv"))))
                .pipeline(new LineagePipeline("20260908T091400Z-7f3a", "customers-load", "load",
                        Optional.of(now), Optional.of(now.plusSeconds(30))))
                .destination(new LineageDestination("bigquery", "project.dataset.customers",
                        Optional.empty(), Optional.empty()))
                .audit(new LineageAudit(100, 98, 2, "sha256:contract"))
                .build();
    }

    static LineageEvent pipelineOnlyEvent() {
        return LineageEvent.builder()
                .pipeline(new LineagePipeline("20260908T091400Z-7f3a", "customers-load", "load",
                        Optional.empty(), Optional.empty()))
                .build();
    }

    @Test
    void emitTakesACompleteEvent() {
        assertThatCode(() -> emitter().emit(completeEvent())).doesNotThrowAnyException();
    }

    @Test
    void emitTakesAnEventWithOnlyAPipeline() {
        assertThatCode(() -> emitter().emit(pipelineOnlyEvent())).doesNotThrowAnyException();
    }

    @Test
    void eachEmittedEventReachesTheBackendOnceWhereObservable() {
        LineageEmitter emitter = emitter();
        emitter.emit(completeEvent());
        emitter.emit(pipelineOnlyEvent());

        delivered().ifPresent(count -> assertThat(count).as("events delivered").isEqualTo(2));
    }
}
