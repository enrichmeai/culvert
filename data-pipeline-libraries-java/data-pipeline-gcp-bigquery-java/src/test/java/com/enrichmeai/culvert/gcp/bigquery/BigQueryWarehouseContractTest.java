package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracttests.WarehouseContractTest;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldValue;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.Schema;
import com.google.cloud.bigquery.Table;
import com.google.cloud.bigquery.TableId;
import com.google.cloud.bigquery.TableResult;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Contract-test wiring for {@link BigQueryWarehouse}.
 *
 * <p>Extends {@link WarehouseContractTest} (Sprint-5 abstract base) and
 * provides a stub-backed {@link BigQueryWarehouse} so all inherited contract
 * methods execute without real GCP credentials or network.
 *
 * <p>BigQuery requires table names in {@code dataset.table} or
 * {@code project.dataset.table} form — bare unqualified names are rejected
 * by {@link BigQueryWarehouse#parseFqtn(String)} before the client is
 * called. {@link #knownTable()} and {@link #missingTable()} therefore
 * supply {@code dataset.table} qualified names; both methods are
 * overridden from the base defaults (T15.4 deviation documented in the
 * module README).
 *
 * <p>Uses plain {@code Mockito.mock()} (lenient by default) rather than
 * {@code @Mock + MockitoExtension} so that stubs set up unconditionally in
 * {@link #warehouse()} are not flagged as unnecessary by strict stubbing
 * when some tests (e.g. {@code nullSqlRejected}) exercise only the SUT's
 * argument validation and never touch the mocked client.
 *
 * <p>Sprint-15 deliverable (T15.4, issue #78).
 */
class BigQueryWarehouseContractTest extends WarehouseContractTest {

    private static final String PROJECT_ID = "contract-project";
    private static final String KNOWN_TABLE = "contract_ds.contract_test_table";
    private static final String MISSING_TABLE = "contract_ds.contract_missing_table";

    /**
     * BigQuery requires {@code dataset.table} qualified names; override the
     * base default of a bare (unqualified) identifier.
     */
    @Override
    protected String knownTable() {
        return KNOWN_TABLE;
    }

    /**
     * BigQuery requires {@code dataset.table} qualified names; override the
     * base default of a bare (unqualified) identifier.
     */
    @Override
    protected String missingTable() {
        return MISSING_TABLE;
    }

    @Override
    protected Warehouse warehouse() {
        BigQuery client = mock(BigQuery.class);

        // --- query stub: return one row {id: "1"} for any SQL ---
        Schema schema = Schema.of(
                Field.of("id", com.google.cloud.bigquery.StandardSQLTypeName.INT64));
        FieldValueList row = FieldValueList.of(
                List.of(FieldValue.of(FieldValue.Attribute.PRIMITIVE, "1")));
        @SuppressWarnings("unchecked")
        TableResult result = mock(TableResult.class);
        when(result.getSchema()).thenReturn(schema);
        when(result.iterateAll()).thenReturn(List.of(row));
        try {
            when(client.query(any(QueryJobConfiguration.class))).thenReturn(result);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("mock setup interrupted", e);
        }

        // --- tableExists stubs ---
        // knownTable: parseFqtn("contract_ds.contract_test_table") → TableId.of(PROJECT_ID, "contract_ds", "contract_test_table")
        Table knownTable = mock(Table.class);
        when(client.getTable(TableId.of(PROJECT_ID, "contract_ds", "contract_test_table")))
                .thenReturn(knownTable);

        // missingTable: parseFqtn resolves to TableId(PROJECT_ID, "contract_ds", "contract_missing_table") → null
        when(client.getTable(TableId.of(PROJECT_ID, "contract_ds", "contract_missing_table")))
                .thenReturn(null);

        return new BigQueryWarehouse(PROJECT_ID, client);
    }
}
