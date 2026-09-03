package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryTableWarehouse;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Regression tests for external review finding #2: re-running the same extract
 * used to double the data.
 *
 * <p>{@code loadFromUri} built a BigQuery {@code LoadJobConfiguration} with only
 * a schema and a format, so BigQuery applied its own default of
 * {@code WRITE_APPEND}. Nothing in the contract, the call site, or the
 * job-control record recorded that a re-run had appended a second copy — the
 * table just quietly had twice the rows.
 *
 * <p>These tests use {@link InMemoryTableWarehouse}, which actually holds rows,
 * rather than {@code RecordingWarehouse}, which records calls and returns a
 * canned count. The distinction matters: the claim under test is about what
 * ends up in the table, and a double that only records calls cannot falsify it.
 */
class IngestionRunnerIdempotencyTest {

    private static final String SOURCE_URI =
            "gs://landing/generic/customers/generic_customers_20260601.csv";
    private static final String TARGET_TABLE = "proj.odp_generic.customers";
    private static final String STAGING_PREFIX = "gs://staging-bucket/staging";
    private static final String ERROR_PREFIX = "gs://error-bucket/errors";
    private static final String CSV_HEADER =
            "customer_id,first_name,last_name,ssn,dob,status,created_date";

    private static final List<String> ROWS = List.of(
            "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
            "cust-2,Alan,Turing,987-65-4321,1912-06-23,A,2020-02-01");

    private InMemoryBlobStore blobStore;
    private InMemoryTableWarehouse warehouse;
    private RecordingJobControlRepository jobControlRepository;
    private IngestionRunner runner;

    @BeforeEach
    void setUp() {
        blobStore = new InMemoryBlobStore();
        warehouse = new InMemoryTableWarehouse(blobStore);
        jobControlRepository = new RecordingJobControlRepository();
        runner = new IngestionRunner(
                blobStore, warehouse, jobControlRepository, STAGING_PREFIX, ERROR_PREFIX);
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260601", CSV_HEADER, ROWS));
    }

    @Test
    void runningTheSameExtractTwiceLeavesOneCopyOfTheData() {
        IngestionResult first = runner.run(new IngestionRequest(
                "run-1", "customers", SOURCE_URI, "20260601", TARGET_TABLE));
        assertThat(first.loadedRowCount()).isEqualTo(2);
        assertThat(warehouse.rowsIn(TARGET_TABLE)).hasSize(2);

        // Same extract date, fresh run id — what a retry actually looks like.
        IngestionResult second = runner.run(new IngestionRequest(
                "run-2", "customers", SOURCE_URI, "20260601", TARGET_TABLE));
        assertThat(second.loadedRowCount()).isEqualTo(2);

        // The whole point: two, not four.
        assertThat(warehouse.rowsIn(TARGET_TABLE)).hasSize(2);
        assertThat(warehouse.rowsIn(TARGET_TABLE))
                .extracting(row -> row.get("customer_id"))
                .containsExactlyInAnyOrder("cust-1", "cust-2");

        // And the surviving copy is the LATEST run's, not a stale first attempt.
        assertThat(warehouse.rowsIn(TARGET_TABLE))
                .allSatisfy(row -> assertThat(row.get("_run_id")).isEqualTo("run-2"));
    }

    @Test
    void aDifferentExtractDateIsAddedRatherThanReplacing() {
        runner.run(new IngestionRequest(
                "run-1", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        // A second, genuinely different extract must NOT be treated as a re-run.
        // This is the guard against "fix duplication by truncating the table",
        // which would silently destroy every other extract already loaded.
        String juneSecondUri = "gs://landing/generic/customers/generic_customers_20260602.csv";
        blobStore.seed(juneSecondUri, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260602", CSV_HEADER,
                List.of("cust-3,Grace,Hopper,555-55-5555,1906-12-09,A,2020-03-01")));

        runner.run(new IngestionRequest(
                "run-2", "customers", juneSecondUri, "20260602", TARGET_TABLE));

        assertThat(warehouse.rowsIn(TARGET_TABLE)).hasSize(3);
        assertThat(warehouse.rowsIn(TARGET_TABLE))
                .extracting(row -> row.get("customer_id"))
                .containsExactlyInAnyOrder("cust-1", "cust-2", "cust-3");
    }

    @Test
    void theLoadIssuesAnExplicitDeleteForTheExtractDateBeforeAppending() {
        runner.run(new IngestionRequest(
                "run-1", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        // Asserted directly so the mechanism is pinned, not just its effect:
        // on an empty table the delete is a no-op and the row-count tests above
        // would pass even if it were never issued.
        assertThat(warehouse.executedSql)
                .singleElement()
                .asString()
                .contains("DELETE FROM " + TARGET_TABLE)
                .contains("_extract_date = @extract_date");
    }

    @Test
    void aFailedRunLeavesNoRowsBehindForTheRetryToDuplicate() {
        // Trailer declares 3 records but one is a repeated header line that the
        // parser silently skips, so the run aborts before writing (finding #3).
        String badUri = "gs://landing/generic/customers/generic_customers_20260603.csv";
        blobStore.seed(badUri, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260603", CSV_HEADER,
                List.of(ROWS.get(0), ROWS.get(1), CSV_HEADER)));

        org.assertj.core.api.Assertions.assertThatThrownBy(() -> runner.run(new IngestionRequest(
                        "run-bad", "customers", badUri, "20260603", TARGET_TABLE)))
                .isInstanceOf(ReconciliationMismatchException.class);

        assertThat(warehouse.rowsIn(TARGET_TABLE)).isEmpty();
        assertThat(warehouse.executedSql).isEmpty();
    }

    @Test
    void auditColumnsAreWrittenSoDownstreamModelsCanJoin() {
        runner.run(new IngestionRequest(
                "run-1", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        Map<String, Object> row = warehouse.rowsIn(TARGET_TABLE).get(0);
        assertThat(row).containsKeys("_run_id", "_extract_date", "_processed_at");
        assertThat(row.get("_extract_date")).isEqualTo("2026-06-01");
    }
}
