package com.enrichmeai.culvert.gcp.pubsub;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static com.enrichmeai.culvert.gcp.pubsub.PubSubCostTracker.BYTES_PER_TIB;
import static com.enrichmeai.culvert.gcp.pubsub.PubSubCostTracker.THROUGHPUT_COST_USD_PER_TIB;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link PubSubCostTracker}. FinOpsSink is mocked — no live GCP.
 *
 * <p>DoD assertions (issue #70):
 * <ul>
 *   <li>{@link #trackPublishMapsToCorrectCostMetricsFields()} — messageCount +
 *       totalBytes → billedMessagesCount + billedBytesWritten + non-zero
 *       estimatedCostUsd.</li>
 *   <li>{@link #trackSubscribeMirrorsTrackPublishLogic()} — same shape for
 *       subscribe.</li>
 *   <li>FinOpsSink.record called exactly once per invocation (all tests).</li>
 *   <li>Zero/negative input → zero cost + WARN + sink.record still called once.</li>
 * </ul>
 */
@ExtendWith(MockitoExtension.class)
class PubSubCostTrackerTest {

    private static final String RUN_ID = "run-pubsub-test-001";

    @Mock
    private FinOpsSink sink;

    private FinOpsTag sampleTag() {
        return FinOpsTag.of("test-system", "test", "cc-test", "test-owner", RUN_ID);
    }

    private PubSubCostTracker newTracker() {
        return new PubSubCostTracker(sink);
    }

    // -------------------------------------------------------------------------
    // DoD: trackPublish → billedMessagesCount + billedBytesWritten + non-zero USD
    // -------------------------------------------------------------------------

    @Test
    void trackPublishMapsToCorrectCostMetricsFields() {
        long messageCount = 1_000L;
        long totalBytes = 2L * BYTES_PER_TIB; // 2 TiB

        newTracker().trackPublish(messageCount, totalBytes, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedMessagesCount()).isEqualTo(messageCount);
        assertThat(metrics.billedBytesWritten()).isEqualTo(totalBytes);
        assertThat(metrics.billedBytesScanned()).isZero();
        assertThat(metrics.billedBytesStored()).isZero();

        // 2 TiB * $40/TiB = $80
        double expectedCostUsd = (double) totalBytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-9));
        assertThat(metrics.estimatedCostUsd()).isCloseTo(80.0, within(1e-9));
    }

    @Test
    void trackPublishPassesTagToSink() {
        FinOpsTag tag = sampleTag();
        newTracker().trackPublish(100L, BYTES_PER_TIB, RUN_ID, tag);

        ArgumentCaptor<FinOpsTag> tagCaptor = ArgumentCaptor.forClass(FinOpsTag.class);
        verify(sink).record(any(CostMetrics.class), tagCaptor.capture());
        assertThat(tagCaptor.getValue()).isSameAs(tag);
    }

    // -------------------------------------------------------------------------
    // DoD: trackSubscribe mirrors trackPublish logic
    // -------------------------------------------------------------------------

    @Test
    void trackSubscribeMirrorsTrackPublishLogic() {
        long messageCount = 500L;
        long totalBytes = BYTES_PER_TIB; // 1 TiB

        newTracker().trackSubscribe(messageCount, totalBytes, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedMessagesCount()).isEqualTo(messageCount);
        assertThat(metrics.billedBytesWritten()).isEqualTo(totalBytes);

        // 1 TiB * $40/TiB = $40
        double expectedCostUsd = (double) totalBytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-9));
        assertThat(metrics.estimatedCostUsd()).isCloseTo(40.0, within(1e-9));
    }

    @Test
    void trackSubscribePassesTagToSink() {
        FinOpsTag tag = sampleTag();
        newTracker().trackSubscribe(50L, BYTES_PER_TIB, RUN_ID, tag);

        ArgumentCaptor<FinOpsTag> tagCaptor = ArgumentCaptor.forClass(FinOpsTag.class);
        verify(sink).record(any(CostMetrics.class), tagCaptor.capture());
        assertThat(tagCaptor.getValue()).isSameAs(tag);
    }

    // -------------------------------------------------------------------------
    // DoD: zero/negative input → zero cost + WARN + sink.record called once
    // -------------------------------------------------------------------------

    @Test
    void trackPublishZeroBytesRecordsZeroCostAndCallsSinkOnce() {
        newTracker().trackPublish(100L, 0L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
        // message count still recorded
        assertThat(captor.getValue().billedMessagesCount()).isEqualTo(100L);
    }

    @Test
    void trackPublishZeroMessageCountRecordsZeroMessagesAndCallsSinkOnce() {
        newTracker().trackPublish(0L, BYTES_PER_TIB, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedMessagesCount()).isZero();
        // cost comes from bytes, not messages
        assertThat(captor.getValue().estimatedCostUsd()).isGreaterThan(0.0);
    }

    @Test
    void trackPublishNegativeInputsRecordZeroCostAndCallsSinkOnce() {
        newTracker().trackPublish(-10L, -500L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedMessagesCount()).isZero();
        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void trackSubscribeZeroBytesRecordsZeroCostAndCallsSinkOnce() {
        newTracker().trackSubscribe(50L, 0L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void trackSubscribeNegativeInputsRecordZeroCostAndCallsSinkOnce() {
        newTracker().trackSubscribe(-5L, -200L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedMessagesCount()).isZero();
        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    // -------------------------------------------------------------------------
    // Constructor validation
    // -------------------------------------------------------------------------

    @Test
    void constructorRejectsNullSink() {
        assertThatThrownBy(() -> new PubSubCostTracker(null))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("sink");
    }

    @Test
    void trackPublishRejectsNullRunId() {
        assertThatThrownBy(() -> newTracker().trackPublish(1L, 1L, null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackPublishRejectsNullTag() {
        assertThatThrownBy(() -> newTracker().trackPublish(1L, 1L, RUN_ID, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackSubscribeRejectsNullRunId() {
        assertThatThrownBy(() -> newTracker().trackSubscribe(1L, 1L, null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackSubscribeRejectsNullTag() {
        assertThatThrownBy(() -> newTracker().trackSubscribe(1L, 1L, RUN_ID, null))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // Rate-constant sanity checks
    // -------------------------------------------------------------------------

    @Test
    void bytesPerTibIsCorrectBinaryDefinition() {
        assertThat(BYTES_PER_TIB).isEqualTo(1L << 40);
    }

    @Test
    void throughputCostPerTibIsExpectedRate() {
        assertThat(THROUGHPUT_COST_USD_PER_TIB).isEqualTo(40.00);
    }
}
