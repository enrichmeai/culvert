package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.enrichmeai.culvert.contracttests.AuditEventPublisherContractTest;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryException;
import com.google.cloud.bigquery.QueryJobConfiguration;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link BigQueryAuditEventPublisher} against the shared
 * {@link AuditEventPublisherContractTest}: a mocked {@link BigQuery} client
 * (the seam {@code BigQueryAuditEventPublisherTest} uses) whose {@code query}
 * accepts each INSERT and counts it, or fails every one with a
 * {@link BigQueryException}. The publisher writes through, so each accepted
 * INSERT is an acknowledged event.
 */
class BigQueryAuditEventPublisherContractTest extends AuditEventPublisherContractTest {

    private int inserts;

    @Override
    protected AuditEventPublisher publisher() {
        BigQuery client = mock(BigQuery.class);
        try {
            when(client.query(any(QueryJobConfiguration.class))).thenAnswer(inv -> {
                inserts++;
                return null;
            });
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
        return new BigQueryAuditEventPublisher(client, "contract-project", "job_control", "audit_events");
    }

    @Override
    protected AuditEventPublisher failingPublisher() {
        BigQuery client = mock(BigQuery.class);
        try {
            when(client.query(any(QueryJobConfiguration.class)))
                    .thenThrow(new BigQueryException(503, "BigQuery unavailable"));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
        return new BigQueryAuditEventPublisher(client, "contract-project", "job_control", "audit_events");
    }

    @Override
    protected int delivered() {
        return inserts;
    }
}
