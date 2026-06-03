package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.ARCHIVE_STORAGE_USD_PER_GIB;
import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.BYTES_PER_GIB;
import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.COLDLINE_STORAGE_USD_PER_GIB;
import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.NEARLINE_STORAGE_USD_PER_GIB;
import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.STANDARD_STORAGE_USD_PER_GIB;
import static com.enrichmeai.culvert.gcp.gcs.GcsCostTracker.WRITE_COST_USD_PER_GIB;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link GcsCostTracker}. FinOpsSink is mocked — no live GCP.
 *
 * <p>DoD assertions (issue #70):
 * <ul>
 *   <li>{@link #trackUploadMapsBytesWrittenToCorrectCostMetricsFields()} —
 *       bytesWritten → billedBytesWritten + non-zero estimatedCostUsd.</li>
 *   <li>{@link #trackStorageClassStandardMapsToCorrectFields()} etc. —
 *       bytesStored → billedBytesStored + non-zero estimatedCostUsd for each
 *       of Standard/Nearline/Coldline/Archive.</li>
 *   <li>FinOpsSink.record called exactly once per invocation (all tests).</li>
 *   <li>Zero/negative input → zero cost + WARN + sink.record still called once.</li>
 * </ul>
 */
@ExtendWith(MockitoExtension.class)
class GcsCostTrackerTest {

    private static final String RUN_ID = "run-gcs-test-001";

    @Mock
    private FinOpsSink sink;

    private FinOpsTag sampleTag() {
        return FinOpsTag.of("test-system", "test", "cc-test", "test-owner", RUN_ID);
    }

    private GcsCostTracker newTracker() {
        return new GcsCostTracker(sink);
    }

    // -------------------------------------------------------------------------
    // DoD: trackUpload → billedBytesWritten + non-zero estimatedCostUsd
    // -------------------------------------------------------------------------

    @Test
    void trackUploadMapsBytesWrittenToCorrectCostMetricsFields() {
        long bytesWritten = 2L * BYTES_PER_GIB; // 2 GiB

        newTracker().trackUpload(bytesWritten, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedBytesWritten()).isEqualTo(bytesWritten);
        assertThat(metrics.billedBytesStored()).isZero();
        assertThat(metrics.billedMessagesCount()).isZero();

        double expectedCostUsd = (double) bytesWritten / (double) BYTES_PER_GIB * WRITE_COST_USD_PER_GIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackUploadPassesTagToSink() {
        FinOpsTag tag = sampleTag();
        newTracker().trackUpload(BYTES_PER_GIB, RUN_ID, tag);

        ArgumentCaptor<FinOpsTag> tagCaptor = ArgumentCaptor.forClass(FinOpsTag.class);
        verify(sink).record(any(CostMetrics.class), tagCaptor.capture());
        assertThat(tagCaptor.getValue()).isSameAs(tag);
    }

    // -------------------------------------------------------------------------
    // DoD: trackStorageClass for each storage class → non-zero estimatedCostUsd
    // -------------------------------------------------------------------------

    @Test
    void trackStorageClassStandardMapsToCorrectFields() {
        long bytesStored = 10L * BYTES_PER_GIB; // 10 GiB

        newTracker().trackStorageClass(bytesStored, "STANDARD", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedBytesStored()).isEqualTo(bytesStored);
        assertThat(metrics.billedBytesWritten()).isZero();

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * STANDARD_STORAGE_USD_PER_GIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackStorageClassNearlineMapsToCorrectFields() {
        long bytesStored = 5L * BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, "NEARLINE", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.billedBytesStored()).isEqualTo(bytesStored);

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * NEARLINE_STORAGE_USD_PER_GIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackStorageClassColdlineMapsToCorrectFields() {
        long bytesStored = 100L * BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, "COLDLINE", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.billedBytesStored()).isEqualTo(bytesStored);

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * COLDLINE_STORAGE_USD_PER_GIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackStorageClassArchiveMapsToCorrectFields() {
        long bytesStored = 1000L * BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, "ARCHIVE", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.billedBytesStored()).isEqualTo(bytesStored);

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * ARCHIVE_STORAGE_USD_PER_GIB;
        assertThat(metrics.estimatedCostUsd()).isGreaterThan(0.0);
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackStorageClassIsCaseInsensitive() {
        long bytesStored = BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, "standard", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * STANDARD_STORAGE_USD_PER_GIB;
        assertThat(captor.getValue().estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    // -------------------------------------------------------------------------
    // DoD: zero/negative input → zero cost + WARN + sink.record called once
    // -------------------------------------------------------------------------

    @Test
    void trackUploadZeroBytesRecordsZeroCostAndCallsSinkOnce() {
        newTracker().trackUpload(0L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void trackUploadNegativeBytesRecordsZeroCostAndCallsSinkOnce() {
        newTracker().trackUpload(-100L, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void trackStorageClassZeroBytesRecordsZeroCostAndCallsSinkOnce() {
        newTracker().trackStorageClass(0L, "STANDARD", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesStored()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void trackStorageClassUnknownClassFallsBackToStandardAndCallsSinkOnce() {
        long bytesStored = BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, "UNKNOWN_CLASS", RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * STANDARD_STORAGE_USD_PER_GIB;
        assertThat(captor.getValue().estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    @Test
    void trackStorageClassNullStorageClassFallsBackToStandardAndCallsSinkOnce() {
        long bytesStored = BYTES_PER_GIB;

        newTracker().trackStorageClass(bytesStored, null, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        double expectedCostUsd = (double) bytesStored / (double) BYTES_PER_GIB * STANDARD_STORAGE_USD_PER_GIB;
        assertThat(captor.getValue().estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    // -------------------------------------------------------------------------
    // Constructor validation
    // -------------------------------------------------------------------------

    @Test
    void constructorRejectsNullSink() {
        assertThatThrownBy(() -> new GcsCostTracker(null))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("sink");
    }

    @Test
    void trackUploadRejectsNullRunId() {
        assertThatThrownBy(() -> newTracker().trackUpload(BYTES_PER_GIB, null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackUploadRejectsNullTag() {
        assertThatThrownBy(() -> newTracker().trackUpload(BYTES_PER_GIB, RUN_ID, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackStorageClassRejectsNullRunId() {
        assertThatThrownBy(() -> newTracker().trackStorageClass(BYTES_PER_GIB, "STANDARD", null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void trackStorageClassRejectsNullTag() {
        assertThatThrownBy(() -> newTracker().trackStorageClass(BYTES_PER_GIB, "STANDARD", RUN_ID, null))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // Rate-constant sanity checks
    // -------------------------------------------------------------------------

    @Test
    void bytesPerGibIsCorrectBinaryDefinition() {
        assertThat(BYTES_PER_GIB).isEqualTo(1L << 30);
    }

    @Test
    void storageClassRatesAreInDescendingOrder() {
        // Standard > Nearline > Coldline > Archive
        assertThat(STANDARD_STORAGE_USD_PER_GIB).isGreaterThan(NEARLINE_STORAGE_USD_PER_GIB);
        assertThat(NEARLINE_STORAGE_USD_PER_GIB).isGreaterThan(COLDLINE_STORAGE_USD_PER_GIB);
        assertThat(COLDLINE_STORAGE_USD_PER_GIB).isGreaterThan(ARCHIVE_STORAGE_USD_PER_GIB);
    }
}
