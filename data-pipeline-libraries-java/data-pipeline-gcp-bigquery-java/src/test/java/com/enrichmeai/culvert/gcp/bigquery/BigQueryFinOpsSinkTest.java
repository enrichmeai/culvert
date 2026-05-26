package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryError;
import com.google.cloud.bigquery.InsertAllRequest;
import com.google.cloud.bigquery.InsertAllResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryFinOpsSink}. Mocks the BigQuery client so no
 * real GCP credentials or network are required.
 */
@ExtendWith(MockitoExtension.class)
class BigQueryFinOpsSinkTest {

    private static final String PROJECT_ID = "my-project";
    private static final String DATASET = "finops";
    private static final String TABLE = "cost_metrics";

    @Mock
    private BigQuery client;

    @Mock
    private InsertAllResponse response;

    private BigQueryFinOpsSink newSink() {
        return new BigQueryFinOpsSink(client, PROJECT_ID, DATASET, TABLE);
    }

    private CostMetrics sampleMetrics() {
        return CostMetrics.builder("run-1")
                .estimatedCostUsd(0.42)
                .billedBytesScanned(1_000_000L)
                .billedBytesWritten(500_000L)
                .slotMillis(2_500L)
                .labels(Map.of("dataset", "warehouse", "team", "platform"))
                .timestamp(Instant.parse("2026-01-15T10:30:00Z"))
                .build();
    }

    private FinOpsTag sampleTag() {
        return new FinOpsTag(
                "retail-fdp", "prod", "cc-1234", "platform-team", "run-1",
                Map.of("business_unit", "retail", "feature_flag", "exp_42"));
    }

    // --- happy paths -------------------------------------------------------

    @Test
    void recordCallsInsertAllOnce() {
        when(response.hasErrors()).thenReturn(false);
        when(client.insertAll(any(InsertAllRequest.class))).thenReturn(response);

        BigQueryFinOpsSink sink = newSink();
        sink.record(sampleMetrics(), sampleTag());

        verify(client).insertAll(any(InsertAllRequest.class));
    }

    @Test
    void rowCarriesAllCostMetricsAndTagFields() {
        BigQueryFinOpsSink sink = newSink();
        Map<String, Object> row = sink.toRow(sampleMetrics(), sampleTag());

        // FinOpsTag columns
        assertThat(row).containsEntry("system", "retail-fdp");
        assertThat(row).containsEntry("environment", "prod");
        assertThat(row).containsEntry("cost_center", "cc-1234");
        assertThat(row).containsEntry("owner", "platform-team");
        assertThat(row).containsEntry("tag_run_id", "run-1");

        // CostMetrics columns
        assertThat(row).containsEntry("run_id", "run-1");
        assertThat(row).containsEntry("estimated_cost_usd", 0.42);
        assertThat(row).containsEntry("billed_bytes_scanned", 1_000_000L);
        assertThat(row).containsEntry("billed_bytes_written", 500_000L);
        assertThat(row).containsEntry("slot_millis", 2_500L);
        assertThat(row).containsEntry("timestamp", "2026-01-15T10:30:00Z");
    }

    @Test
    void labelsAndExtraTagsFlattenToKeyValueRecords() {
        BigQueryFinOpsSink sink = newSink();
        Map<String, Object> row = sink.toRow(sampleMetrics(), sampleTag());

        @SuppressWarnings("unchecked")
        List<Map<String, String>> labels = (List<Map<String, String>>) row.get("labels");
        assertThat(labels).hasSize(2);
        assertThat(labels).allSatisfy(entry ->
                assertThat(entry).containsKeys("key", "value"));

        @SuppressWarnings("unchecked")
        List<Map<String, String>> extra = (List<Map<String, String>>) row.get("tag_extra");
        assertThat(extra).hasSize(2);
    }

    @Test
    void emptyLabelsAndExtraProduceEmptyLists() {
        BigQueryFinOpsSink sink = newSink();
        CostMetrics zeroMetrics = CostMetrics.zero("run-2");
        FinOpsTag zeroTag = FinOpsTag.of("sys", "dev", "cc", "owner", "run-2");

        Map<String, Object> row = sink.toRow(zeroMetrics, zeroTag);

        assertThat((List<?>) row.get("labels")).isEmpty();
        assertThat((List<?>) row.get("tag_extra")).isEmpty();
    }

    @Test
    void targetTableMatchesConstructedTriple() {
        when(response.hasErrors()).thenReturn(false);
        when(client.insertAll(any(InsertAllRequest.class))).thenReturn(response);

        BigQueryFinOpsSink sink = newSink();
        sink.record(sampleMetrics(), sampleTag());

        ArgumentCaptor<InsertAllRequest> captor =
                ArgumentCaptor.forClass(InsertAllRequest.class);
        verify(client).insertAll(captor.capture());

        InsertAllRequest req = captor.getValue();
        assertThat(req.getTable().getProject()).isEqualTo(PROJECT_ID);
        assertThat(req.getTable().getDataset()).isEqualTo(DATASET);
        assertThat(req.getTable().getTable()).isEqualTo(TABLE);
        assertThat(req.getRows()).hasSize(1);
    }

    // --- error paths -------------------------------------------------------

    @Test
    void partialFailureSurfacesAsFinOpsInsertException() {
        when(response.hasErrors()).thenReturn(true);
        when(response.getInsertErrors()).thenReturn(
                Map.of(0L, List.of(new BigQueryError(
                        "invalidQuery", "us-central1", "bad column"))));
        when(client.insertAll(any(InsertAllRequest.class))).thenReturn(response);

        BigQueryFinOpsSink sink = newSink();

        assertThatThrownBy(() -> sink.record(sampleMetrics(), sampleTag()))
                .isInstanceOf(BigQueryFinOpsSink.FinOpsInsertException.class)
                .hasMessageContaining("run-1");
    }

    @Test
    void nullMetricsRejected() {
        BigQueryFinOpsSink sink = newSink();
        assertThatThrownBy(() -> sink.record(null, sampleTag()))
                .isInstanceOf(NullPointerException.class);
        verify(client, never()).insertAll(any(InsertAllRequest.class));
    }

    @Test
    void nullTagsRejected() {
        BigQueryFinOpsSink sink = newSink();
        assertThatThrownBy(() -> sink.record(sampleMetrics(), null))
                .isInstanceOf(NullPointerException.class);
        verify(client, never()).insertAll(any(InsertAllRequest.class));
    }

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new BigQueryFinOpsSink(null, PROJECT_ID, DATASET, TABLE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullProject() {
        assertThatThrownBy(() -> new BigQueryFinOpsSink(client, null, DATASET, TABLE))
                .isInstanceOf(NullPointerException.class);
    }

    // --- multi-call ordering ----------------------------------------------

    @Test
    void multipleSequentialRecordCallsEachInsertOneRow() {
        when(response.hasErrors()).thenReturn(false);
        when(client.insertAll(any(InsertAllRequest.class))).thenReturn(response);

        BigQueryFinOpsSink sink = newSink();
        sink.record(sampleMetrics(), sampleTag());
        sink.record(sampleMetrics(), sampleTag());
        sink.record(sampleMetrics(), sampleTag());

        ArgumentCaptor<InsertAllRequest> captor =
                ArgumentCaptor.forClass(InsertAllRequest.class);
        verify(client, org.mockito.Mockito.times(3)).insertAll(captor.capture());
        assertThat(captor.getAllValues()).allSatisfy(req ->
                assertThat(req.getRows()).hasSize(1));
    }
}
