package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryError;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldValue;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics.LoadStatistics;
import com.google.cloud.bigquery.JobStatus;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.Schema;
import com.google.cloud.bigquery.Table;
import com.google.cloud.bigquery.TableId;
import com.google.cloud.bigquery.TableResult;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigInteger;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryWarehouse}. Mocks
 * {@link com.google.cloud.bigquery.BigQuery} so no real GCP credentials or
 * network are required.
 */
@ExtendWith(MockitoExtension.class)
class BigQueryWarehouseTest {

    private static final String PROJECT_ID = "my-project";

    @Mock
    private BigQuery client;

    // --- query -------------------------------------------------------------

    @Test
    void queryStreamsRowsAsMaps() throws InterruptedException {
        Schema schema = Schema.of(
                Field.of("id", com.google.cloud.bigquery.StandardSQLTypeName.INT64),
                Field.of("name", com.google.cloud.bigquery.StandardSQLTypeName.STRING));

        FieldValueList row1 = FieldValueList.of(List.of(
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "1"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "alice")));
        FieldValueList row2 = FieldValueList.of(List.of(
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "2"),
                FieldValue.of(FieldValue.Attribute.PRIMITIVE, "bob")));

        TableResult result = org.mockito.Mockito.mock(TableResult.class);
        when(result.getSchema()).thenReturn(schema);
        when(result.iterateAll()).thenReturn(List.of(row1, row2));
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(result);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT id, name FROM t WHERE id = @id",
                Map.of("id", 1L));

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> first = rows.next();
        assertThat(first).containsEntry("id", "1");
        assertThat(first).containsEntry("name", "alice");
        Map<String, Object> second = rows.next();
        assertThat(second).containsEntry("name", "bob");
        assertThat(rows.hasNext()).isFalse();

        ArgumentCaptor<QueryJobConfiguration> cfg = ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(cfg.capture());
        assertThat(cfg.getValue().getQuery()).contains("WHERE id = @id");
        assertThat(cfg.getValue().getNamedParameters()).containsKey("id");
    }

    // --- execute -----------------------------------------------------------

    @Test
    void executeRunsDmlAndIgnoresResult() throws InterruptedException {
        TableResult result = org.mockito.Mockito.mock(TableResult.class);
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(result);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        warehouse.execute("DELETE FROM my-project.ds.t WHERE id = @id",
                Map.of("id", 99L));

        ArgumentCaptor<QueryJobConfiguration> cfg = ArgumentCaptor.forClass(QueryJobConfiguration.class);
        verify(client).query(cfg.capture());
        assertThat(cfg.getValue().getQuery()).startsWith("DELETE FROM");
    }

    // --- loadFromUri -------------------------------------------------------

    @Test
    void loadFromUriReturnsOutputRowsFromLoadStatistics() throws InterruptedException {
        EntitySchema entity = EntitySchema.of("customer", List.of(
                SchemaField.required("id", "INT64"),
                SchemaField.nullable("name", "STRING")));

        Job submitted = org.mockito.Mockito.mock(Job.class);
        Job completed = org.mockito.Mockito.mock(Job.class);
        LoadStatistics stats = org.mockito.Mockito.mock(LoadStatistics.class);
        when(submitted.waitFor()).thenReturn(completed);
        when(completed.getStatistics()).thenReturn(stats);
        when(stats.getOutputRows()).thenReturn(42L);
        when(client.create(any(JobInfo.class))).thenReturn(submitted);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        long rows = warehouse.loadFromUri(
                "gs://bucket/customers.csv",
                "my-project.ds.customers",
                entity);

        assertThat(rows).isEqualTo(42L);

        ArgumentCaptor<JobInfo> jobCaptor = ArgumentCaptor.forClass(JobInfo.class);
        verify(client).create(jobCaptor.capture());
        assertThat(jobCaptor.getValue().getConfiguration()).isNotNull();
    }

    // --- merge -------------------------------------------------------------

    @Test
    void mergeThrowsUnsupportedOperationPendingColumnAwareSql() {
        // Column-aware MERGE (BigQuery doesn't accept `SET t.* = s.*`) is
        // deferred to sprint-4. The contract method exists so that callers
        // get a clear "use execute() with explicit SQL" signal rather than
        // silent data loss.
        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThatThrownBy(() -> warehouse.merge(
                        "my-project.ds.staging",
                        "my-project.ds.fact",
                        List.of("id")))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("sprint-4")
                .hasMessageContaining("execute");
    }

    @Test
    void mergeRejectsEmptyKeys() {
        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThatThrownBy(() -> warehouse.merge("a.b.c", "a.b.d", List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("key");
    }

    // --- copy --------------------------------------------------------------

    @Test
    void copyReturnsTargetRowCountAfterJobCompletes() throws InterruptedException {
        Job submitted = org.mockito.Mockito.mock(Job.class);
        Job completed = org.mockito.Mockito.mock(Job.class);
        when(submitted.waitFor()).thenReturn(completed);
        when(client.create(any(JobInfo.class))).thenReturn(submitted);

        Table target = org.mockito.Mockito.mock(Table.class);
        when(target.getNumRows()).thenReturn(BigInteger.valueOf(100L));
        when(client.getTable(any(TableId.class))).thenReturn(target);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        long copied = warehouse.copy(
                "my-project.ds.source",
                "my-project.ds.target");

        assertThat(copied).isEqualTo(100L);
        verify(client).create(any(JobInfo.class));
    }

    // --- tableExists -------------------------------------------------------

    @Test
    void tableExistsReturnsTrueWhenTablePresent() {
        Table table = org.mockito.Mockito.mock(Table.class);
        when(client.getTable(any(TableId.class))).thenReturn(table);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThat(warehouse.tableExists("my-project.ds.customers")).isTrue();
    }

    @Test
    void tableExistsReturnsFalseWhenClientReturnsNull() {
        when(client.getTable(any(TableId.class))).thenReturn(null);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThat(warehouse.tableExists("my-project.ds.missing")).isFalse();
    }

    @Test
    void tableExistsReturnsFalseOn404() {
        BigQueryException notFound = new BigQueryException(404, "table not found");
        when(client.getTable(any(TableId.class))).thenThrow(notFound);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThat(warehouse.tableExists("my-project.ds.gone")).isFalse();
    }

    // --- fqtn parsing ------------------------------------------------------

    @Test
    void unqualifiedTwoPartFqtnFallsBackToConfiguredProjectId() {
        when(client.getTable(any(TableId.class))).thenReturn(null);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        warehouse.tableExists("ds.customers");

        ArgumentCaptor<TableId> idCaptor = ArgumentCaptor.forClass(TableId.class);
        verify(client).getTable(idCaptor.capture());
        assertThat(idCaptor.getValue().getProject()).isEqualTo(PROJECT_ID);
        assertThat(idCaptor.getValue().getDataset()).isEqualTo("ds");
        assertThat(idCaptor.getValue().getTable()).isEqualTo("customers");
    }

    // --- error paths -------------------------------------------------------

    @Test
    void queryWrapsInterruptedExceptionAndSetsInterruptFlag() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class)))
                .thenThrow(new InterruptedException("aborted"));

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        try {
            assertThatThrownBy(() -> warehouse.query("SELECT 1", Map.of()))
                    .isInstanceOf(RuntimeException.class)
                    .hasMessageContaining("interrupted");
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            // Clear the interrupt flag so subsequent tests in this JVM
            // aren't affected.
            Thread.interrupted();
        }
    }

    @Test
    void loadFromUriPropagatesJobStatusError() throws InterruptedException {
        EntitySchema entity = EntitySchema.of("c", List.of(SchemaField.required("id", "INT64")));

        Job submitted = org.mockito.Mockito.mock(Job.class);
        Job completed = org.mockito.Mockito.mock(Job.class);
        JobStatus status = org.mockito.Mockito.mock(JobStatus.class);
        BigQueryError err = new BigQueryError("invalid", "us", "schema mismatch");
        lenient().when(status.getError()).thenReturn(err);
        when(submitted.waitFor()).thenReturn(completed);
        lenient().when(completed.getStatus()).thenReturn(status);
        when(client.create(any(JobInfo.class))).thenReturn(submitted);

        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        assertThatThrownBy(() -> warehouse.loadFromUri(
                        "gs://bucket/bad.csv",
                        "my-project.ds.target",
                        entity))
                .isInstanceOf(BigQueryException.class);
    }

    // --- AutoCloseable -----------------------------------------------------

    @Test
    void closeDelegatesToClient() throws Exception {
        BigQueryWarehouse warehouse = new BigQueryWarehouse(PROJECT_ID, client);
        warehouse.close();
        verify(client).close();
    }
}
