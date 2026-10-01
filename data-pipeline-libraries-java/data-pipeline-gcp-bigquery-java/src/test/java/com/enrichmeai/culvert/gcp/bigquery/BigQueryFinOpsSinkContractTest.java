package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracttests.FinOpsSinkContractTest;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.InsertAllRequest;
import com.google.cloud.bigquery.InsertAllResponse;

import java.util.OptionalInt;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link BigQueryFinOpsSink} against the shared {@link FinOpsSinkContractTest}:
 * a mocked {@link BigQuery} client (the seam {@code BigQueryFinOpsSinkTest}
 * uses) whose {@code insertAll} accepts every row and counts it.
 */
class BigQueryFinOpsSinkContractTest extends FinOpsSinkContractTest {

    private int rows;

    @Override
    protected FinOpsSink sink() {
        BigQuery client = mock(BigQuery.class);
        InsertAllResponse ok = mock(InsertAllResponse.class);
        when(ok.hasErrors()).thenReturn(false);
        when(client.insertAll(any(InsertAllRequest.class))).thenAnswer(inv -> {
            InsertAllRequest request = inv.getArgument(0);
            rows += request.getRows().size();
            return ok;
        });
        return new BigQueryFinOpsSink(client, "contract-project", "job_control", "cost_metrics");
    }

    @Override
    protected OptionalInt delivered() {
        return OptionalInt.of(rows);
    }
}
