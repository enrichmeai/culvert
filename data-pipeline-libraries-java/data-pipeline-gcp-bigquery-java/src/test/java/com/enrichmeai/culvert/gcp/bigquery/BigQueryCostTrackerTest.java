package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobId;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics;
import com.google.cloud.bigquery.JobStatistics.LoadStatistics;
import com.google.cloud.bigquery.JobStatistics.QueryStatistics;
import com.google.cloud.bigquery.QueryJobConfiguration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker.BYTES_PER_TIB;
import static com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker.LOAD_COST_USD_PER_TIB;
import static com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker.QUERY_COST_USD_PER_TIB;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryCostTracker}. All GCP calls are mocked —
 * no live credentials or network are required.
 *
 * <p>DoD assertions (issue #69):
 * <ul>
 *   <li>{@link #queryJobMapsToCorrectCostMetricsFields()} — DoD bullet 2:
 *       QueryStatistics.getTotalBytesBilled → billedBytesScanned,
 *       getTotalSlotMs → slotMillis.</li>
 *   <li>{@link #loadJobMapsToCorrectCostMetricsFields()} — DoD bullet 3:
 *       LoadStatistics.getOutputBytes → billedBytesWritten.</li>
 *   <li>{@link #nullBytesBilledTreatedAsZeroAndLogsWarn()} — DoD bullet 4:
 *       null statistics fields → zero + WARN.</li>
 *   <li>{@link #estimateDryRunReturnsCostMetricsWithPositiveEstimate()} — DoD bullet 5:
 *       estimateDryRun returns CostMetrics with estimatedCostUsd > 0 for non-zero bytes.</li>
 * </ul>
 */
@ExtendWith(MockitoExtension.class)
class BigQueryCostTrackerTest {

    private static final String RUN_ID = "run-test-001";

    @Mock
    private BigQuery client;

    @Mock
    private FinOpsSink sink;

    private FinOpsTag sampleTag() {
        return FinOpsTag.of("test-system", "test", "cc-test", "test-owner", RUN_ID);
    }

    private BigQueryCostTracker newTracker() {
        return new BigQueryCostTracker(client, sink);
    }

    // -------------------------------------------------------------------------
    // DoD bullet 2: query job — bytesBilled + slotMillis mapping
    // -------------------------------------------------------------------------

    @Test
    void queryJobMapsToCorrectCostMetricsFields() {
        long bytesBilled = 2_000_000_000L; // 2 GB
        long slotMs = 50_000L;

        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(bytesBilled);
        when(qs.getTotalSlotMs()).thenReturn(slotMs);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(qs);

        newTracker().trackJob(job, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedBytesScanned()).isEqualTo(bytesBilled);
        assertThat(metrics.slotMillis()).isEqualTo(slotMs);
        assertThat(metrics.billedBytesWritten()).isZero();

        double expectedCostUsd = (double) bytesBilled / (double) BYTES_PER_TIB * QUERY_COST_USD_PER_TIB;
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-9));
    }

    @Test
    void queryJobPassesTagToSink() {
        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(1_000_000L);
        when(qs.getTotalSlotMs()).thenReturn(1_000L);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(qs);

        FinOpsTag tag = sampleTag();
        newTracker().trackJob(job, RUN_ID, tag);

        ArgumentCaptor<FinOpsTag> tagCaptor = ArgumentCaptor.forClass(FinOpsTag.class);
        verify(sink).record(any(CostMetrics.class), tagCaptor.capture());
        assertThat(tagCaptor.getValue()).isSameAs(tag);
    }

    // -------------------------------------------------------------------------
    // DoD bullet 3: load job — outputBytes mapping
    // -------------------------------------------------------------------------

    @Test
    void loadJobMapsToCorrectCostMetricsFields() {
        long outputBytes = 500_000_000L; // 500 MB

        LoadStatistics ls = mock(LoadStatistics.class);
        when(ls.getOutputBytes()).thenReturn(outputBytes);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(ls);

        newTracker().trackJob(job, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.runId()).isEqualTo(RUN_ID);
        assertThat(metrics.billedBytesWritten()).isEqualTo(outputBytes);
        assertThat(metrics.billedBytesScanned()).isZero();
        assertThat(metrics.slotMillis()).isZero();

        double expectedCostUsd = (double) outputBytes / (double) BYTES_PER_TIB * LOAD_COST_USD_PER_TIB;
        assertThat(metrics.estimatedCostUsd()).isCloseTo(expectedCostUsd, within(1e-12));
    }

    // -------------------------------------------------------------------------
    // DoD bullet 4: null fields → zero + WARN
    // -------------------------------------------------------------------------

    @Test
    void nullBytesBilledTreatedAsZeroAndLogsWarn() {
        // getTotalBytesBilled() returns null
        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(null);
        when(qs.getTotalSlotMs()).thenReturn(1_000L);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(qs);

        newTracker().trackJob(job, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        CostMetrics metrics = captor.getValue();
        assertThat(metrics.billedBytesScanned()).isZero();
        assertThat(metrics.estimatedCostUsd()).isZero();
        // slotMillis should still be captured
        assertThat(metrics.slotMillis()).isEqualTo(1_000L);
    }

    @Test
    void nullSlotMsTreatedAsZeroAndLogsWarn() {
        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(1_000_000L);
        when(qs.getTotalSlotMs()).thenReturn(null);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(qs);

        newTracker().trackJob(job, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().slotMillis()).isZero();
    }

    @Test
    void nullOutputBytesTreatedAsZeroAndLogsWarn() {
        LoadStatistics ls = mock(LoadStatistics.class);
        when(ls.getOutputBytes()).thenReturn(null);

        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(ls);

        newTracker().trackJob(job, RUN_ID, sampleTag());

        ArgumentCaptor<CostMetrics> captor = ArgumentCaptor.forClass(CostMetrics.class);
        verify(sink).record(captor.capture(), any(FinOpsTag.class));

        assertThat(captor.getValue().billedBytesWritten()).isZero();
        assertThat(captor.getValue().estimatedCostUsd()).isZero();
    }

    @Test
    void nullJobStatisticsEmitsNoMetricsAndLogsWarn() {
        Job job = mock(Job.class);
        when(job.getStatistics()).thenReturn(null);
        // Provide a non-null jobId for the WARN log
        when(job.getJobId()).thenReturn(JobId.of("test-project", "test-job-123"));

        newTracker().trackJob(job, RUN_ID, sampleTag());

        verify(sink, never()).record(any(CostMetrics.class), any(FinOpsTag.class));
    }

    // -------------------------------------------------------------------------
    // DoD bullet 5: estimateDryRun → CostMetrics with estimatedCostUsd > 0
    // -------------------------------------------------------------------------

    @Test
    void estimateDryRunReturnsCostMetricsWithPositiveEstimate() throws InterruptedException {
        long dryRunBytes = 10L * 1_099_511_627_776L; // 10 TiB

        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(dryRunBytes);

        Job dryRunJob = mock(Job.class);
        when(dryRunJob.waitFor()).thenReturn(dryRunJob);
        when(dryRunJob.getStatistics()).thenReturn(qs);

        when(client.create(any(JobInfo.class))).thenReturn(dryRunJob);

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(
                "SELECT COUNT(*) FROM `my-project.my-dataset.my-table`").build();

        CostMetrics result = newTracker().estimateDryRun(config, RUN_ID);

        assertThat(result.runId()).isEqualTo(RUN_ID);
        assertThat(result.billedBytesScanned()).isEqualTo(dryRunBytes);
        assertThat(result.estimatedCostUsd()).isGreaterThan(0.0);

        // Verify correct formula: 10 TiB * $5.00/TiB = $50.00
        assertThat(result.estimatedCostUsd()).isCloseTo(50.0, within(1e-9));

        // Dry-run estimate: other fields should be zero
        assertThat(result.slotMillis()).isZero();
        assertThat(result.billedBytesWritten()).isZero();
    }

    @Test
    void estimateDryRunFallsBackToTotalBytesProcessedWhenBilledIsNull() throws InterruptedException {
        long processedBytes = 5L * 1_099_511_627_776L; // 5 TiB

        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(null);
        when(qs.getTotalBytesProcessed()).thenReturn(processedBytes);

        Job dryRunJob = mock(Job.class);
        when(dryRunJob.waitFor()).thenReturn(dryRunJob);
        when(dryRunJob.getStatistics()).thenReturn(qs);

        when(client.create(any(JobInfo.class))).thenReturn(dryRunJob);

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(
                "SELECT COUNT(*) FROM `my-project.dataset.table`").build();

        CostMetrics result = newTracker().estimateDryRun(config, RUN_ID);

        // Falls back to processedBytes → 5 TiB * $5.00/TiB = $25.00
        assertThat(result.billedBytesScanned()).isEqualTo(processedBytes);
        assertThat(result.estimatedCostUsd()).isCloseTo(25.0, within(1e-9));
    }

    @Test
    void estimateDryRunReturnsZeroWhenBothBytesFieldsAreNull() throws InterruptedException {
        QueryStatistics qs = mock(QueryStatistics.class);
        when(qs.getTotalBytesBilled()).thenReturn(null);
        when(qs.getTotalBytesProcessed()).thenReturn(null);

        Job dryRunJob = mock(Job.class);
        when(dryRunJob.waitFor()).thenReturn(dryRunJob);
        when(dryRunJob.getStatistics()).thenReturn(qs);

        when(client.create(any(JobInfo.class))).thenReturn(dryRunJob);

        QueryJobConfiguration config = QueryJobConfiguration.newBuilder(
                "SELECT 1").build();

        CostMetrics result = newTracker().estimateDryRun(config, RUN_ID);

        assertThat(result.estimatedCostUsd()).isZero();
        assertThat(result.billedBytesScanned()).isZero();
    }

    // -------------------------------------------------------------------------
    // Constructor validation
    // -------------------------------------------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new BigQueryCostTracker(null, sink))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("client");
    }

    @Test
    void constructorRejectsNullSink() {
        assertThatThrownBy(() -> new BigQueryCostTracker(client, null))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("sink");
    }

    @Test
    void trackJobRejectsNullJob() {
        assertThatThrownBy(() -> newTracker().trackJob(null, RUN_ID, sampleTag()))
                .isInstanceOf(NullPointerException.class);
        verify(sink, never()).record(any(), any());
    }

    @Test
    void trackJobRejectsNullRunId() {
        Job job = mock(Job.class);
        assertThatThrownBy(() -> newTracker().trackJob(job, null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
        verify(sink, never()).record(any(), any());
    }

    @Test
    void trackJobRejectsNullTag() {
        Job job = mock(Job.class);
        assertThatThrownBy(() -> newTracker().trackJob(job, RUN_ID, null))
                .isInstanceOf(NullPointerException.class);
        verify(sink, never()).record(any(), any());
    }

    // -------------------------------------------------------------------------
    // Rate-constant sanity checks
    // -------------------------------------------------------------------------

    @Test
    void bytesPerTibIsCorrectBinaryDefinition() {
        // 2^40 = 1,099,511,627,776
        assertThat(BYTES_PER_TIB).isEqualTo(1L << 40);
    }

    @Test
    void queryCostPerTibIsExpectedOnDemandRate() {
        assertThat(QUERY_COST_USD_PER_TIB).isEqualTo(5.00);
    }
}
