package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.audit.AuditRecord;
import com.enrichmeai.culvert.itsupport.BigQueryEmulatorContainer;
import com.google.cloud.bigquery.BigQuery;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.Instant;
import java.util.Iterator;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration tests for {@link BigQueryAuditEventPublisher} exercised against a
 * real BigQuery emulator (goccy/bigquery-emulator) via the it-support
 * {@link BigQueryEmulatorContainer} fixture.
 *
 * <p>Where {@code BigQueryAuditEventPublisherTest} mocks the {@link BigQuery}
 * client and asserts on the SQL that gets built, this IT drives the adapter
 * end-to-end: it creates the audit table, publishes records, then queries them
 * back and asserts on the returned rows.
 *
 * <h2>Run this test</h2>
 * <pre>{@code
 * mvn -f data-pipeline-libraries-java/pom.xml \
 *     -pl data-pipeline-gcp-bigquery-java -am \
 *     -P it verify
 * }</pre>
 *
 * <p>This test is <strong>architect-run only</strong> — it requires Docker +
 * the goccy/bigquery-emulator image and is therefore excluded from the standard
 * {@code mvn test} (surefire) run. It executes only under {@code mvn -P it verify}
 * via failsafe (all {@code *IT.java} files). This matches the established
 * pattern in {@link BigQueryWarehouseIT}.
 *
 * <h2>Known emulator risk</h2>
 * <p>The goccy emulator's support for named parameters ({@code @param_name}) in
 * DML {@code INSERT} statements is not fully documented. If the emulator rejects
 * named parameters in this context, the workaround is to switch the IT-only
 * write path to literal value substitution (using a
 * {@link BigQueryWarehouse#execute}-style helper that the warehouse IT already
 * tests). The unit test ({@link BigQueryAuditEventPublisherTest}) remains the
 * primary correctness gate; this IT confirms end-to-end emulator compatibility.
 * See also the {@code BigQueryCostTrackerIT} note about dry-run population, which
 * similarly cannot be verified without a live endpoint.
 *
 * <p>Sprint-14 deliverable for issue #95 (T14.6). Architect-run only.
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class BigQueryAuditEventPublisherIT {

    @Container
    static final BigQueryEmulatorContainer EMULATOR = new BigQueryEmulatorContainer();

    private BigQueryAuditEventPublisher publisher;
    private BigQueryWarehouse warehouse;  // used for CREATE TABLE + SELECT
    private String dataset;
    private String auditTable;

    @BeforeAll
    void setUp() {
        BigQuery bq = EMULATOR.newClient();
        dataset    = EMULATOR.getDatasetId();
        auditTable = "audit_events";

        publisher = new BigQueryAuditEventPublisher(
                bq, EMULATOR.getProjectId(), dataset, auditTable);

        // warehouse is used for DDL + read-back; BigQueryAuditEventPublisher
        // only writes (no query method), so we drive SELECT through the warehouse.
        warehouse = new BigQueryWarehouse(EMULATOR.getProjectId(), bq);

        // CREATE the audit table schema.
        String fqtn = "`" + EMULATOR.getProjectId() + "." + dataset + "." + auditTable + "`";
        warehouse.execute(
                "CREATE TABLE " + fqtn + " ("
                + "run_id                        STRING NOT NULL, "
                + "pipeline_name                 STRING NOT NULL, "
                + "entity_type                   STRING NOT NULL, "
                + "source_file                   STRING NOT NULL, "
                + "record_count                  INT64  NOT NULL, "
                + "processed_timestamp           TIMESTAMP NOT NULL, "
                + "processing_duration_seconds   FLOAT64 NOT NULL, "
                + "success                       BOOL NOT NULL, "
                + "error_count                   INT64 NOT NULL, "
                + "audit_hash                    STRING, "
                + "metadata_json                 STRING, "
                + "published_at                  TIMESTAMP"
                + ")",
                Map.of());
    }

    private AuditRecord sampleRecord(String runId) {
        return AuditRecord.builder()
                .runId(runId)
                .pipelineName("customer-ingest")
                .entityType("customer")
                .sourceFile("gs://my-bucket/customers.csv")
                .recordCount(500L)
                .processedTimestamp(Instant.parse("2026-06-05T10:00:00Z"))
                .processingDurationSeconds(2.0)
                .success(true)
                .errorCount(0L)
                .auditHash("abc-hash")
                .metadata(Map.of("partition", "2026-06-05"))
                .build();
    }

    @Test
    void publishedRowIsQueryableFromAuditTable() {
        publisher.publish(sampleRecord("it-run-001"));
        // Surface any swallowed write failure immediately at the write step,
        // rather than as a confusing "missing row" assertion later.
        assertThat(publisher.auditFailureCount())
                .as("publish should not have swallowed an error")
                .isZero();
        publisher.flush(); // no-op but contract-required call

        String fqtn = "`" + EMULATOR.getProjectId() + "." + dataset + "." + auditTable + "`";
        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT run_id, pipeline_name, entity_type, success, record_count "
                + "FROM " + fqtn + " WHERE run_id = 'it-run-001'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> row = rows.next();
        assertThat(row).containsEntry("pipeline_name", "customer-ingest");
        assertThat(row).containsEntry("entity_type", "customer");
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void multiplePublishCallsProduceMultipleRows() {
        publisher.publish(sampleRecord("it-run-002a"));
        publisher.publish(sampleRecord("it-run-002b"));
        assertThat(publisher.auditFailureCount())
                .as("both publishes should succeed")
                .isZero();
        publisher.flush();

        String fqtn = "`" + EMULATOR.getProjectId() + "." + dataset + "." + auditTable + "`";
        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT run_id FROM " + fqtn
                + " WHERE run_id IN ('it-run-002a', 'it-run-002b') ORDER BY run_id",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        rows.next();
        assertThat(rows.hasNext()).isTrue();
        rows.next();
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void metadataJsonFieldContainsSerializedMap() {
        publisher.publish(sampleRecord("it-run-003"));
        assertThat(publisher.auditFailureCount())
                .as("publish should not have swallowed an error")
                .isZero();

        String fqtn = "`" + EMULATOR.getProjectId() + "." + dataset + "." + auditTable + "`";
        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT metadata_json FROM " + fqtn + " WHERE run_id = 'it-run-003'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> row = rows.next();
        Object metaJson = row.get("metadata_json");
        assertThat(metaJson).isNotNull();
        assertThat(metaJson.toString()).contains("partition");
    }
}
