package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.contracttests.WarehouseContractTest;
import software.amazon.awssdk.services.athena.AthenaClient;
import software.amazon.awssdk.services.athena.model.ColumnInfo;
import software.amazon.awssdk.services.athena.model.Datum;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionResponse;
import software.amazon.awssdk.services.athena.model.GetQueryResultsRequest;
import software.amazon.awssdk.services.athena.model.GetQueryResultsResponse;
import software.amazon.awssdk.services.athena.model.GetTableMetadataRequest;
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

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link AthenaWarehouse}.
 *
 * <p>Extends {@link WarehouseContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link AthenaWarehouse} so all inherited contract
 * methods execute without real AWS credentials or network. Mirrors
 * {@code BigQueryWarehouseContractTest} in {@code data-pipeline-gcp-bigquery-java}.
 *
 * <p>Every {@code query()}/{@code tableExists()} call goes through
 * {@code StartQueryExecution} + {@code GetQueryExecution} (stubbed to
 * SUCCEEDED on first poll) + {@code GetQueryResults} (stubbed to return one
 * header row + one data row, per Athena's actual response shape) or
 * {@code GetTableMetadata} respectively — the mock does not discriminate by
 * SQL text, so every {@code query()} call sees the same single {@code {id: "1"}}
 * row regardless of {@link #knownTable()}.
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension} so that stubs set up unconditionally in
 * {@link #warehouse()} are not flagged as unnecessary by strict stubbing when
 * some tests (e.g. {@code nullSqlRejected}) exercise only the SUT's argument
 * validation and never touch the mocked client.
 *
 * <p>Sprint-21 deliverable (T21.5, issue #149).
 */
class AthenaWarehouseContractTest extends WarehouseContractTest {

    private static final String DATABASE = "contract_db";
    private static final String OUTPUT_LOCATION = "s3://contract-bucket/athena-results/";
    private static final String QUERY_EXECUTION_ID = "contract-query-id";

    @Override
    protected Warehouse warehouse() {
        AthenaClient client = mock(AthenaClient.class);

        // --- query stub: StartQueryExecution -> GetQueryExecution(SUCCEEDED) -> GetQueryResults ---
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

        ResultSetMetadata metadata = ResultSetMetadata.builder()
                .columnInfo(ColumnInfo.builder().name("id").label("id").type("varchar").build())
                .build();
        // Athena echoes the column header as the first data row; the real
        // value ("1") is the second row. AthenaWarehouse must skip row 0.
        Row headerRow = Row.builder().data(Datum.builder().varCharValue("id").build()).build();
        Row dataRow = Row.builder().data(Datum.builder().varCharValue("1").build()).build();
        when(client.getQueryResults(any(GetQueryResultsRequest.class)))
                .thenReturn(GetQueryResultsResponse.builder()
                        .resultSet(ResultSet.builder()
                                .resultSetMetadata(metadata)
                                .rows(List.of(headerRow, dataRow))
                                .build())
                        .build());

        // --- tableExists stubs ---
        // knownTable(): GetTableMetadata succeeds.
        when(client.getTableMetadata(GetTableMetadataRequest.builder()
                        .catalogName("AwsDataCatalog")
                        .databaseName(DATABASE)
                        .tableName("contract_test_table")
                        .build()))
                .thenReturn(software.amazon.awssdk.services.athena.model.GetTableMetadataResponse.builder()
                        .tableMetadata(TableMetadata.builder().name("contract_test_table").build())
                        .build());

        // missingTable(): GetTableMetadata throws MetadataException (Athena/Glue's
        // "table not found" signal — contrast with BigQuery's null return).
        when(client.getTableMetadata(GetTableMetadataRequest.builder()
                        .catalogName("AwsDataCatalog")
                        .databaseName(DATABASE)
                        .tableName("contract_missing_table")
                        .build()))
                .thenThrow(MetadataException.builder().message("not found").build());

        return new AthenaWarehouse(client, DATABASE, OUTPUT_LOCATION);
    }
}
