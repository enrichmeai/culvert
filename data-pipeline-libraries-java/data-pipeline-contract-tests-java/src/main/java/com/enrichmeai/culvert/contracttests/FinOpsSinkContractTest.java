package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * Contract tests every {@link FinOpsSink} implementation must pass.
 *
 * <p>The interface says {@code record} takes cost metrics with their
 * attribution tags, once per cost-incurring operation, and that a sink may
 * batch. The framework's own default, {@code NoOpFinOpsSink}, discards every
 * record, and the suite treats that as legal. So the cases are: a zero-cost
 * and a fully populated record are both taken without an exception, and, where
 * the binding can observe its backend ({@link #delivered()}), each record
 * reaches it once. A batching sink reports what it has delivered so far.
 *
 * <p>Nothing about failure or {@code null} is tested: the interface is silent
 * on both, and the no-op default accepts anything.
 */
public abstract class FinOpsSinkContractTest {

    private static final String RUN_ID = "20260908T091400Z-7f3a";

    protected abstract FinOpsSink sink();

    /**
     * How many records the backend has received, or empty for an implementation
     * whose backend the binding cannot observe (the no-op default).
     */
    protected OptionalInt delivered() {
        return OptionalInt.empty();
    }

    static CostMetrics fullMetrics() {
        return CostMetrics.builder(RUN_ID)
                .estimatedCostUsd(0.0125)
                .billedBytesScanned(10_485_760L)
                .billedBytesWritten(1_048_576L)
                .billedBytesStored(0L)
                .billedMessagesCount(250L)
                .slotMillis(1_200L)
                .computeUnits(0.5)
                .labels(Map.of("stage", "load"))
                .timestamp(Instant.parse("2026-09-08T09:14:30Z"))
                .build();
    }

    static FinOpsTag fullTags() {
        return new FinOpsTag("generic", "int", "cc-data", "data-team", RUN_ID, Map.of("entity", "customers"));
    }

    @Test
    void recordTakesAZeroCostRecord() {
        assertThatCode(() -> sink().record(CostMetrics.zero(RUN_ID),
                FinOpsTag.of("generic", "int", "cc-data", "data-team", RUN_ID)))
                .doesNotThrowAnyException();
    }

    @Test
    void recordTakesAFullyPopulatedRecord() {
        assertThatCode(() -> sink().record(fullMetrics(), fullTags())).doesNotThrowAnyException();
    }

    @Test
    void eachRecordReachesTheBackendOnceWhereObservable() {
        FinOpsSink sink = sink();
        sink.record(CostMetrics.zero(RUN_ID), FinOpsTag.of("generic", "int", "cc-data", "data-team", RUN_ID));
        sink.record(fullMetrics(), fullTags());

        delivered().ifPresent(count -> assertThat(count).as("records delivered").isEqualTo(2));
    }
}
