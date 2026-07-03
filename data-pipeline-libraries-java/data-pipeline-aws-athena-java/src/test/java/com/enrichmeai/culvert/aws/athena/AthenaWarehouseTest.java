package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.schema.EntitySchema;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import software.amazon.awssdk.services.athena.AthenaClient;
import software.amazon.awssdk.services.athena.model.ColumnInfo;
import software.amazon.awssdk.services.athena.model.Datum;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionResponse;
import software.amazon.awssdk.services.athena.model.GetQueryResultsRequest;
import software.amazon.awssdk.services.athena.model.GetQueryResultsResponse;
import software.amazon.awssdk.services.athena.model.GetTableMetadataRequest;
import software.amazon.awssdk.services.athena.model.GetTableMetadataResponse;
import software.amazon.awssdk.services.athena.model.MetadataException;
import software.amazon.awssdk.services.athena.model.QueryExecution;
import software.amazon.awssdk.services.athena.model.QueryExecutionState;
import software.amazon.awssdk.services.athena.model.QueryExecutionStatus;
import software.amazon.awssdk.services.athena.model.ResultSet;
import software.amazon.awssdk.services.athena.model.ResultSetMetadata;
import software.amazon.awssdk.services.athena.model.Row;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionResponse;
import software.amazon.awssdk.services.athena.model.TableMetadata;

import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mocked-client unit tests for {@link AthenaWarehouse}.
 *
 * <p>Covers all implemented contract methods (query, execute, copy,
 * tableExists), the two documented {@link UnsupportedOperationException}
 * methods (merge, loadFromUri), null-argument rejection, and the
 * query-failure path (FAILED state -&gt; {@link AthenaWarehouse.AthenaQueryFailedException}).
 * The shared {@link com.enrichmeai.culvert.contracttests.WarehouseContractTest}
 * suite (bound in {@link AthenaWarehouseContractTest}) covers the
 * cross-warehouse contract shape; this class covers Athena-specific request
 * wiring (paginated GetQueryResults, header-row skip, GetTableMetadata
 * routing) that the shared suite deliberately does not know about.
 *
 * <p>Real AWS round-trips are out of scope for this module (no LocalStack
 * Athena support) — see the class Javadoc on {@link AthenaWarehouse}.
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AthenaWarehouseTest {

    private static final String DATABASE = "analytics";
    private static final String OUTPUT_LOCATION = "s3://athena-results-bucket/prefix/";
    private static final String QUERY_EXECUTION_ID = "query-123";

    @Mock
    private AthenaClient client;

    private AthenaWarehouse warehouse;

    @BeforeEach
    void setUp() {
        warehouse = new AthenaWarehouse(client, DATABASE, OUTPUT_LOCATION);
    }

    private void stubStartAndSucceed() {
        when(client.startQueryExecution(any(StartQueryExecutionRequest.class)))
                .thenReturn(StartQueryExecutionResponse.builder()
                        .queryExecutionId(QUERY_EXECUTION_ID)
                        .build());
        when(client.getQueryExecution(any(GetQueryExecutionRequest.class)))
                .thenReturn(GetQueryExecutionResponse.builder()
                        .queryExecution(QueryExecution.builder()
                                .queryExecutionId(QUERY_EXECUTION_ID)
                                .status(QueryExecutionStatus.builder()
                                        .state(QueryExecutionState.SUCCEEDED)
                                        .build())
                                .build())
                        .build());
    }

    private static GetQueryResultsResponse singlePageResult(String columnName, String... dataValues) {
        ResultSetMetadata metadata = ResultSetMetadata.builder()
                .columnInfo(ColumnInfo.builder().name(columnName).label(columnName).type("varchar").build())
                .build();
        Row headerRow = Row.builder().data(Datum.builder().varCharValue(columnName).build()).build();
        var rows = new java.util.ArrayList<Row>();
        rows.add(headerRow);
        for (String value : dataValues) {
            rows.add(Row.builder().data(Datum.builder().varCharValue(value).build()).build());
        }
        return GetQueryResultsResponse.builder()
                .resultSet(ResultSet.builder().resultSetMetadata(metadata).rows(rows).build())
                .build();
    }

    // ------------------------------------------------------------------ //
    // query()
    // ------------------------------------------------------------------ //

    @Test
    void queryStreamsRowsSkippingHeaderRowOnFirstPageOnly() {
        stubStartAndSucceed();
        when(client.getQueryResults(any(GetQueryResultsRequest.class)))
                .thenReturn(singlePageResult("id", "1", "2"));

        Iterator<Map<String, Object>> rows = warehouse.query("SELECT id FROM t", Map.of());

        assertThat(rows.hasNext()).isTrue();
        assertThat(rows.next()).containsEntry("id", "1");
        assertThat(rows.next()).containsEntry("id", "2");
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void queryPaginatesAndOnlySkipsHeaderOnFirstPage() {
        stubStartAndSucceed();

        ResultSetMetadata metadata = ResultSetMetadata.builder()
                .columnInfo(ColumnInfo.builder().name("id").label("id").type("varchar").build())
                .build();
        Row headerRow = Row.builder().data(Datum.builder().varCharValue("id").build()).build();
        Row page1Data = Row.builder().data(Datum.builder().varCharValue("1").build()).build();
        Row page2DataA = Row.builder().data(Datum.builder().varCharValue("2").build()).build();
        Row page2DataB = Row.builder().data(Datum.builder().varCharValue("3").build()).build();

        GetQueryResultsResponse page1 = GetQueryResultsResponse.builder()
                .resultSet(ResultSet.builder().resultSetMetadata(metadata).rows(List.of(headerRow, page1Data)).build())
                .nextToken("page-2-token")
                .build();
        GetQueryResultsResponse page2 = GetQueryResultsResponse.builder()
                .resultSet(ResultSet.builder().resultSetMetadata(metadata).rows(List.of(page2DataA, page2DataB)).build())
                .build();

        when(client.getQueryResults(any(GetQueryResultsRequest.class))).thenReturn(page1, page2);

        Iterator<Map<String, Object>> rows = warehouse.query("SELECT id FROM t", Map.of());
        List<Object> ids = new java.util.ArrayList<>();
        rows.forEachRemaining(row -> ids.add(row.get("id")));

        // Header row skipped only once (page 1); all 3 real data rows present.
        assertThat(ids).containsExactly("1", "2", "3");
        verify(client, times(2)).getQueryResults(any(GetQueryResultsRequest.class));
    }

    @Test
    void queryRejectsNullSql() {
        assertThatNullPointerException().isThrownBy(() -> warehouse.query(null, Map.of()));
    }

    @Test
    void queryRejectsNonEmptyParams() {
        // Athena has no named-parameter binding analogous to BigQuery's;
        // silently dropping caller-supplied bindings would be a correctness
        // risk, so non-empty params must fail loudly rather than be ignored.
        assertThatThrownBy(() -> warehouse.query("SELECT :id", Map.of("id", 1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("named parameter");
    }

    @Test
    void queryFailurePropagatesAsAthenaQueryFailedException() {
        when(client.startQueryExecution(any(StartQueryExecutionRequest.class)))
                .thenReturn(StartQueryExecutionResponse.builder().queryExecutionId(QUERY_EXECUTION_ID).build());
        when(client.getQueryExecution(any(GetQueryExecutionRequest.class)))
                .thenReturn(GetQueryExecutionResponse.builder()
                        .queryExecution(QueryExecution.builder()
                                .queryExecutionId(QUERY_EXECUTION_ID)
                                .status(QueryExecutionStatus.builder()
                                        .state(QueryExecutionState.FAILED)
                                        .stateChangeReason("SYNTAX_ERROR: line 1")
                                        .build())
                                .build())
                        .build());

        assertThatThrownBy(() -> warehouse.query("SELECT bogus", Map.of()))
                .isInstanceOf(AthenaWarehouse.AthenaQueryFailedException.class)
                .hasMessageContaining(QUERY_EXECUTION_ID)
                .hasMessageContaining("FAILED")
                .hasMessageContaining("SYNTAX_ERROR");
    }

    @Test
    void queryCancelledAlsoPropagatesAsFailure() {
        when(client.startQueryExecution(any(StartQueryExecutionRequest.class)))
                .thenReturn(StartQueryExecutionResponse.builder().queryExecutionId(QUERY_EXECUTION_ID).build());
        when(client.getQueryExecution(any(GetQueryExecutionRequest.class)))
                .thenReturn(GetQueryExecutionResponse.builder()
                        .queryExecution(QueryExecution.builder()
                                .queryExecutionId(QUERY_EXECUTION_ID)
                                .status(QueryExecutionStatus.builder()
                                        .state(QueryExecutionState.CANCELLED)
                                        .build())
                                .build())
                        .build());

        assertThatThrownBy(() -> warehouse.query("SELECT 1", Map.of()))
                .isInstanceOf(AthenaWarehouse.AthenaQueryFailedException.class)
                .hasMessageContaining("CANCELLED");
    }

    @Test
    void queryPollsUntilTerminalState() {
        when(client.startQueryExecution(any(StartQueryExecutionRequest.class)))
                .thenReturn(StartQueryExecutionResponse.builder().queryExecutionId(QUERY_EXECUTION_ID).build());

        GetQueryExecutionResponse running = GetQueryExecutionResponse.builder()
                .queryExecution(QueryExecution.builder()
                        .queryExecutionId(QUERY_EXECUTION_ID)
                        .status(QueryExecutionStatus.builder().state(QueryExecutionState.RUNNING).build())
                        .build())
                .build();
        GetQueryExecutionResponse succeeded = GetQueryExecutionResponse.builder()
                .queryExecution(QueryExecution.builder()
                        .queryExecutionId(QUERY_EXECUTION_ID)
                        .status(QueryExecutionStatus.builder().state(QueryExecutionState.SUCCEEDED).build())
                        .build())
                .build();
        when(client.getQueryExecution(any(GetQueryExecutionRequest.class)))
                .thenReturn(running, running, succeeded);
        when(client.getQueryResults(any(GetQueryResultsRequest.class)))
                .thenReturn(singlePageResult("id", "1"));

        Iterator<Map<String, Object>> rows = warehouse.query("SELECT id FROM t", Map.of());

        assertThat(rows.hasNext()).isTrue();
        verify(client, times(3)).getQueryExecution(any(GetQueryExecutionRequest.class));
    }

    // ------------------------------------------------------------------ //
    // execute()
    // ------------------------------------------------------------------ //

    @Test
    void executeSubmitsQueryWithoutFetchingResults() {
        stubStartAndSucceed();

        warehouse.execute("CREATE TABLE t (id INT)", Map.of());

        ArgumentCaptor<StartQueryExecutionRequest> captor = ArgumentCaptor.forClass(StartQueryExecutionRequest.class);
        verify(client).startQueryExecution(captor.capture());
        assertThat(captor.getValue().queryString()).isEqualTo("CREATE TABLE t (id INT)");
        assertThat(captor.getValue().resultConfiguration().outputLocation()).isEqualTo(OUTPUT_LOCATION);
        assertThat(captor.getValue().queryExecutionContext().database()).isEqualTo(DATABASE);
        assertThat(captor.getValue().queryExecutionContext().catalog()).isEqualTo("AwsDataCatalog");
        verify(client, times(0)).getQueryResults(any(GetQueryResultsRequest.class));
    }

    @Test
    void executeRejectsNullSql() {
        assertThatNullPointerException().isThrownBy(() -> warehouse.execute(null, Map.of()));
    }

    @Test
    void executeRejectsNonEmptyParams() {
        assertThatThrownBy(() -> warehouse.execute("INSERT INTO t VALUES (:id)", Map.of("id", 1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("named parameter");
    }

    @Test
    void executeUsesConfiguredWorkGroupWhenSet() {
        AthenaWarehouse withWorkGroup =
                new AthenaWarehouse(client, DATABASE, OUTPUT_LOCATION, "AwsDataCatalog", "my-workgroup");
        stubStartAndSucceed();

        withWorkGroup.execute("SELECT 1", Map.of());

        ArgumentCaptor<StartQueryExecutionRequest> captor = ArgumentCaptor.forClass(StartQueryExecutionRequest.class);
        verify(client).startQueryExecution(captor.capture());
        assertThat(captor.getValue().workGroup()).isEqualTo("my-workgroup");
    }

    // ------------------------------------------------------------------ //
    // copy() — CTAS + follow-up COUNT(*)
    // ------------------------------------------------------------------ //

    @Test
    void copyIssuesCtasThenCountsRows() {
        stubStartAndSucceed();
        when(client.getQueryResults(any(GetQueryResultsRequest.class)))
                .thenReturn(singlePageResult("row_count", "42"));

        long copied = warehouse.copy("src_db.src_table", "dst_db.dst_table");

        assertThat(copied).isEqualTo(42L);
        ArgumentCaptor<StartQueryExecutionRequest> captor = ArgumentCaptor.forClass(StartQueryExecutionRequest.class);
        verify(client, times(2)).startQueryExecution(captor.capture());
        assertThat(captor.getAllValues().get(0).queryString())
                .isEqualTo("CREATE TABLE dst_db.dst_table AS SELECT * FROM src_db.src_table");
        assertThat(captor.getAllValues().get(1).queryString())
                .isEqualTo("SELECT COUNT(*) AS row_count FROM dst_db.dst_table");
    }

    @Test
    void copyRejectsNullArguments() {
        assertThatNullPointerException().isThrownBy(() -> warehouse.copy(null, "t"));
        assertThatNullPointerException().isThrownBy(() -> warehouse.copy("t", null));
    }

    // ------------------------------------------------------------------ //
    // tableExists()
    // ------------------------------------------------------------------ //

    @Test
    void tableExistsTrueWhenGetTableMetadataSucceeds() {
        when(client.getTableMetadata(any(GetTableMetadataRequest.class)))
                .thenReturn(GetTableMetadataResponse.builder()
                        .tableMetadata(TableMetadata.builder().name("customers").build())
                        .build());

        assertThat(warehouse.tableExists("customers")).isTrue();

        ArgumentCaptor<GetTableMetadataRequest> captor = ArgumentCaptor.forClass(GetTableMetadataRequest.class);
        verify(client).getTableMetadata(captor.capture());
        assertThat(captor.getValue().databaseName()).isEqualTo(DATABASE);
        assertThat(captor.getValue().tableName()).isEqualTo("customers");
        assertThat(captor.getValue().catalogName()).isEqualTo("AwsDataCatalog");
    }

    @Test
    void tableExistsFalseWhenGetTableMetadataThrowsMetadataException() {
        when(client.getTableMetadata(any(GetTableMetadataRequest.class)))
                .thenThrow(MetadataException.builder().message("not found").build());

        assertThat(warehouse.tableExists("missing")).isFalse();
    }

    @Test
    void tableExistsAcceptsDatabaseQualifiedNameMatchingConfiguredDatabase() {
        when(client.getTableMetadata(any(GetTableMetadataRequest.class)))
                .thenReturn(GetTableMetadataResponse.builder()
                        .tableMetadata(TableMetadata.builder().name("customers").build())
                        .build());

        assertThat(warehouse.tableExists("analytics.customers")).isTrue();

        ArgumentCaptor<GetTableMetadataRequest> captor = ArgumentCaptor.forClass(GetTableMetadataRequest.class);
        verify(client).getTableMetadata(captor.capture());
        assertThat(captor.getValue().tableName()).isEqualTo("customers");
        assertThat(captor.getValue().databaseName()).isEqualTo(DATABASE);
    }

    @Test
    void tableExistsHonoursDifferentDatabaseQualifierThanConfigured() {
        // Regression guard: the fqtn's own database component must be used,
        // not silently overridden by the warehouse's configured `database`.
        when(client.getTableMetadata(any(GetTableMetadataRequest.class)))
                .thenReturn(GetTableMetadataResponse.builder()
                        .tableMetadata(TableMetadata.builder().name("orders").build())
                        .build());

        assertThat(warehouse.tableExists("otherdb.orders")).isTrue();

        ArgumentCaptor<GetTableMetadataRequest> captor = ArgumentCaptor.forClass(GetTableMetadataRequest.class);
        verify(client).getTableMetadata(captor.capture());
        assertThat(captor.getValue().databaseName()).isEqualTo("otherdb");
        assertThat(captor.getValue().tableName()).isEqualTo("orders");
    }

    @Test
    void tableExistsRejectsNull() {
        assertThatNullPointerException().isThrownBy(() -> warehouse.tableExists(null));
    }

    // ------------------------------------------------------------------ //
    // merge() / loadFromUri() — documented UnsupportedOperationException
    // ------------------------------------------------------------------ //

    @Test
    void mergeThrowsUnsupportedOperationException() {
        assertThatThrownBy(() -> warehouse.merge("src", "dst", List.of("id")))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("MERGE");
    }

    @Test
    void mergeRejectsEmptyKeysBeforeUnsupportedCheck() {
        assertThatThrownBy(() -> warehouse.merge("src", "dst", List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void mergeRejectsNullArguments() {
        assertThatNullPointerException().isThrownBy(() -> warehouse.merge(null, "dst", List.of("id")));
        assertThatNullPointerException().isThrownBy(() -> warehouse.merge("src", null, List.of("id")));
        assertThatNullPointerException().isThrownBy(() -> warehouse.merge("src", "dst", null));
    }

    @Test
    void loadFromUriThrowsUnsupportedOperationException() {
        EntitySchema schema = EntitySchema.of("customer", List.of());
        assertThatThrownBy(() -> warehouse.loadFromUri("s3://bucket/data.parquet", "t", schema))
                .isInstanceOf(UnsupportedOperationException.class)
                .hasMessageContaining("bulk-load");
    }

    @Test
    void loadFromUriRejectsNullArguments() {
        EntitySchema schema = EntitySchema.of("customer", List.of());
        assertThatNullPointerException().isThrownBy(() -> warehouse.loadFromUri(null, "t", schema));
        assertThatNullPointerException().isThrownBy(() -> warehouse.loadFromUri("uri", null, schema));
        assertThatNullPointerException().isThrownBy(() -> warehouse.loadFromUri("uri", "t", null));
    }

    // ------------------------------------------------------------------ //
    // Constructor guards
    // ------------------------------------------------------------------ //

    @Test
    void constructorRejectsNulls() {
        assertThatNullPointerException().isThrownBy(() -> new AthenaWarehouse(null, DATABASE, OUTPUT_LOCATION));
        assertThatNullPointerException().isThrownBy(() -> new AthenaWarehouse(client, null, OUTPUT_LOCATION));
        assertThatNullPointerException().isThrownBy(() -> new AthenaWarehouse(client, DATABASE, null));
    }
}
