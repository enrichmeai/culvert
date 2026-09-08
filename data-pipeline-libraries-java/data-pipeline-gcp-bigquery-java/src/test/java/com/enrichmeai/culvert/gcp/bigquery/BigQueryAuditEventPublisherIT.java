package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.audit.AuditEvent;
import com.enrichmeai.culvert.audit.EventKind;
import com.enrichmeai.culvert.itsupport.BigQueryEmulatorContainer;
import com.google.cloud.bigquery.BigQuery;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.Instant;
import java.time.LocalDate;
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
 * end-to-end: it creates {@code job_control.audit_events} with
 * {@code docs/CONTRACT.md} §4's ten columns, publishes events, then queries
 * them back and asserts on the returned rows.
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
 * <h2>Known emulator risks — this file has NOT been run since the §4 rewrite</h2>
 * <ol>
 *   <li><strong>JSON column + {@code PARSE_JSON}.</strong> §4 types
 *       {@code payload} as {@code JSON} and the publisher writes it via
 *       {@code PARSE_JSON(@payload)}. goccy's support for the {@code JSON} type
 *       and that function is unverified. If the emulator rejects either, the
 *       IT-only workaround is to declare {@code payload STRING} here and read
 *       it back as text — the production DDL stays {@code JSON}, and the unit
 *       test remains the primary correctness gate for the statement shape.</li>
 *   <li><strong>Named parameters in DML {@code INSERT}.</strong> Support for
 *       {@code @param_name} in this context is likewise not fully documented;
 *       the fallback is literal substitution through
 *       {@link BigQueryWarehouse#execute}, which the warehouse IT already
 *       covers.</li>
 * </ol>
 *
 * <p>Sprint-23 audit rebuild; originally issue #95 (T14.6). Architect-run only.
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class BigQueryAuditEventPublisherIT {

    @Container
    static final BigQueryEmulatorContainer EMULATOR = new BigQueryEmulatorContainer();

    private static final Instant EVENT_TS = Instant.parse("2026-06-05T10:00:00Z");

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

        // CREATE the audit_events table — docs/CONTRACT.md §4, ten columns.
        warehouse.execute(
                "CREATE TABLE " + fqtn() + " ("
                + "run_id           STRING    NOT NULL, "
                + "system_id        STRING    NOT NULL, "
                + "entity           STRING    NOT NULL, "
                + "event_kind       STRING    NOT NULL, "
                + "event_ts         TIMESTAMP NOT NULL, "
                + "extract_date     DATE, "
                + "payload          JSON, "
                + "producer         STRING, "
                + "contract_version STRING    NOT NULL, "
                + "environment      STRING"
                + ")",
                Map.of());
    }

    private String fqtn() {
        return "`" + EMULATOR.getProjectId() + "." + dataset + "." + auditTable + "`";
    }

    private static AuditEvent sampleEvent(String runId) {
        return AuditEvent.of(runId, "generic", "customers", EventKind.RUN_START,
                EVENT_TS, Map.of("source_file", "gs://my-bucket/customers.csv"),
                LocalDate.parse("2026-06-04"), "culvert@0.2.0", "int");
    }

    @Test
    void publishedRowIsQueryableFromAuditEvents() {
        publisher.publish(sampleEvent("it-run-001"));
        // A run-level publish now throws on failure, so reaching here already
        // means the write succeeded; the counter assertion documents that.
        assertThat(publisher.auditFailureCount())
                .as("publish should not have failed")
                .isZero();
        publisher.flush(); // no-op but contract-required call

        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT run_id, system_id, entity, event_kind, contract_version, environment "
                + "FROM " + fqtn() + " WHERE run_id = 'it-run-001'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> row = rows.next();
        assertThat(row).containsEntry("system_id", "generic");
        assertThat(row).containsEntry("entity", "customers");
        assertThat(row).containsEntry("event_kind", "RUN_START");
        assertThat(row).containsEntry("contract_version", "1.0.0");
        assertThat(row).containsEntry("environment", "int");
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void multiplePublishCallsProduceMultipleRows() {
        publisher.publish(sampleEvent("it-run-002a"));
        publisher.publish(sampleEvent("it-run-002b"));
        assertThat(publisher.auditFailureCount())
                .as("both publishes should succeed")
                .isZero();
        publisher.flush();

        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT run_id FROM " + fqtn()
                + " WHERE run_id IN ('it-run-002a', 'it-run-002b') ORDER BY run_id",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        rows.next();
        assertThat(rows.hasNext()).isTrue();
        rows.next();
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void payloadRoundTripsAsJson() {
        publisher.publish(AuditEvent.of("it-run-003", "generic", "customers",
                EventKind.RECONCILIATION, EVENT_TS,
                Map.of("expected_count", 500L, "accounted_count", 500L,
                        "reconciled", true)));

        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT payload FROM " + fqtn() + " WHERE run_id = 'it-run-003'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Object payload = rows.next().get("payload");
        assertThat(payload).isNotNull();
        assertThat(payload.toString()).contains("expected_count");
    }

    @Test
    void aggregateEventCarriesItsCountWithoutFailingTheRun() {
        publisher.publish(AuditEvent.of("it-run-004", "generic", "customers",
                EventKind.RECORD_REJECTED, EVENT_TS,
                Map.of("count", 7L, "quarantine_uri", "gs://my-bucket/quarantine/")));
        assertThat(publisher.auditFailureCount()).isZero();

        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT event_kind FROM " + fqtn() + " WHERE run_id = 'it-run-004'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        assertThat(rows.next()).containsEntry("event_kind", "RECORD_REJECTED");
    }
}
