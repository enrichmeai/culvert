package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * End-to-end unit tests for {@link IngestionRunner}: HDR/TRL envelope parse
 * -> CSV parse -> schema validate -> stage+load -> quarantine -> reconcile ->
 * job-control, all against in-memory adapters (no live GCP, no Docker).
 */
class IngestionRunnerTest {

    private static final String SOURCE_URI = "gs://landing/generic/customers/generic_customers_20260601.csv";
    private static final String TARGET_TABLE = "proj.odp_generic.customers";
    private static final String STAGING_PREFIX = "gs://staging-bucket/staging";
    private static final String ERROR_PREFIX = "gs://error-bucket/errors";
    private static final String CSV_HEADER =
            "customer_id,first_name,last_name,ssn,dob,status,created_date";

    private InMemoryBlobStore blobStore;
    private RecordingWarehouse warehouse;
    private RecordingJobControlRepository jobControlRepository;
    private IngestionRunner runner;

    @BeforeEach
    void setUp() {
        blobStore = new InMemoryBlobStore();
        warehouse = new RecordingWarehouse();
        jobControlRepository = new RecordingJobControlRepository();
        runner = new IngestionRunner(blobStore, warehouse, jobControlRepository, STAGING_PREFIX, ERROR_PREFIX);
    }

    @Test
    void allValidRows_loadsAllAndReconciles() {
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                "cust-2,Alan,Turing,987-65-4321,1985-06-23,A,2019-05-05");
        seedSourceFile(rows);
        warehouse.returnRowCount(2);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-1", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.candidateRowCount()).isEqualTo(2);
        assertThat(result.validRowCount()).isEqualTo(2);
        assertThat(result.invalidRowCount()).isZero();
        assertThat(result.loadedRowCount()).isEqualTo(2);
        assertThat(result.reconciliation().isReconciled()).isTrue();

        // Staged NDJSON was written and loaded.
        assertThat(warehouse.loadCalls).hasSize(1);
        String stagingUri = warehouse.loadCalls.get(0).uri();
        assertThat(stagingUri).startsWith(STAGING_PREFIX + "/customers/run-1");
        assertThat(warehouse.loadCalls.get(0).targetTable()).isEqualTo(TARGET_TABLE);

        // No quarantine file since nothing was invalid.
        assertThat(blobStore.writtenUris()).noneMatch(uri -> uri.contains("/quarantine/"));

        // Job control: CREATED -> RUNNING -> SUCCEEDED, no markFailed.
        assertThat(jobControlRepository.job("run-1")).isPresent();
        assertThat(jobControlRepository.statusUpdates).extracting(
                RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING, JobStatus.SUCCEEDED);
        assertThat(jobControlRepository.markFailedCalls).isEmpty();
    }

    @Test
    void invalidRows_areQuarantinedAndValidRowsStillLoad() {
        // NOTE: every field in the customers schema is typed STRING or DATE, and
        // DataQualityTransform only type-checks STRING/INT64/FLOAT64/BOOL (see
        // DataQualityTransform.WIRE_TYPE_MAP) with MISSING_REQUIRED firing only when
        // the map value is Java `null` — a CSV-sourced row always supplies a (possibly
        // empty) String for every header, so it can never be `null`. A schema-level
        // DQ violation is therefore not reachable through this CSV path with this
        // entity's schema; this test instead exercises the field-count-mismatch path
        // (a CsvRowParser-level error), which is the quarantine path CSV rows can
        // actually hit. Schema-violation quarantine is covered directly against
        // DataQualityTransform + InvalidRowAdapter in IngestionRunnerDqQuarantineTest.
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                "cust-2,Alan,Turing"); // too few fields -> CsvRowParser error, not schema violation
        seedSourceFile(rows);
        warehouse.returnRowCount(1);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-2", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.candidateRowCount()).isEqualTo(1);
        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(result.loadedRowCount()).isEqualTo(1);
        // The TRL declares 2 rows but only 1 was well-formed CSV and loaded — this is
        // exactly the mismatch reconciliation exists to catch (mirrors the Python
        // reference's reconciliation warning when quarantined rows reduce the loaded
        // count below the envelope's declared total).
        assertThat(result.reconciliation().isReconciled()).isFalse();
        assertThat(result.reconciliation().expectedCount()).isEqualTo(2);
        assertThat(result.reconciliation().actualCount()).isEqualTo(1);

        // Quarantine file was written.
        assertThat(blobStore.writtenUris()).anyMatch(uri -> uri.contains("/quarantine/run-2/"));

        // markFailed called twice: once by QuarantineHandler for the parse-error
        // quarantine, once for the resulting reconciliation mismatch.
        assertThat(jobControlRepository.markFailedCalls).hasSize(2);
        assertThat(jobControlRepository.markFailedCalls.get(0).errorCode())
                .isEqualTo("DQ_VALIDATION_FAILURE");
        assertThat(jobControlRepository.markFailedCalls.get(0).failureStage())
                .isEqualTo(FailureStage.VALIDATION);
        assertThat(jobControlRepository.markFailedCalls.get(1).errorCode())
                .isEqualTo("RECONCILIATION_MISMATCH");
        assertThat(jobControlRepository.markFailedCalls.get(1).failureStage())
                .isEqualTo(FailureStage.RECONCILIATION);

        // Overall job still succeeds — invalid rows are quarantined, not fatal.
        assertThat(jobControlRepository.statusUpdates).extracting(
                RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING, JobStatus.SUCCEEDED);
    }

    @Test
    void csvFieldCountMismatch_isQuarantinedAsParseError() {
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                "cust-2,Alan,Turing"); // too few fields
        seedSourceFile(rows);
        warehouse.returnRowCount(1);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-3", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.candidateRowCount()).isEqualTo(1);
        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(blobStore.writtenUris()).anyMatch(uri -> uri.contains("/quarantine/run-3/"));
    }

    @Test
    void reconciliationMismatch_marksFailedButDoesNotThrow() {
        List<String> rows = List.of("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01");
        seedSourceFile(rows);
        // Warehouse reports fewer rows loaded than declared (0 instead of 1).
        warehouse.returnRowCount(0);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-4", "customers", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.reconciliation().isReconciled()).isFalse();
        assertThat(result.reconciliation().expectedCount()).isEqualTo(1);
        assertThat(result.reconciliation().actualCount()).isEqualTo(0);

        assertThat(jobControlRepository.markFailedCalls)
                .anyMatch(c -> c.errorCode().equals("RECONCILIATION_MISMATCH")
                        && c.failureStage() == FailureStage.RECONCILIATION);

        // Job control still marks the run as SUCCEEDED at the top level — reconciliation
        // failure is recorded via markFailed but does not abort the run (mirrors the
        // Python reference, which logs a reconciliation warning rather than raising).
        assertThat(jobControlRepository.statusUpdates).extracting(
                RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING, JobStatus.SUCCEEDED);
    }

    @Test
    void malformedEnvelope_marksJobFailedAndPropagates() {
        blobStore.seed(SOURCE_URI, "NOT_AN_ENVELOPE".getBytes(StandardCharsets.UTF_8));

        assertThatThrownBy(() -> runner.run(new IngestionRequest(
                "run-5", "customers", SOURCE_URI, "20260601", TARGET_TABLE)))
                .isInstanceOf(RuntimeException.class);

        assertThat(jobControlRepository.markFailedCalls).hasSize(1);
        assertThat(jobControlRepository.markFailedCalls.get(0).errorCode())
                .isEqualTo("ENVELOPE_VALIDATION_FAILURE");
        assertThat(jobControlRepository.markFailedCalls.get(0).failureStage())
                .isEqualTo(FailureStage.VALIDATION);
        // No load or quarantine attempted after an envelope failure.
        assertThat(warehouse.loadCalls).isEmpty();
    }

    @Test
    void unknownEntity_throwsBeforeTouchingAdapters() {
        assertThatThrownBy(() -> runner.run(new IngestionRequest(
                "run-6", "not-a-real-entity", SOURCE_URI, "20260601", TARGET_TABLE)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Unknown entity");
    }

    private void seedSourceFile(List<String> dataRows) {
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260601", CSV_HEADER, dataRows));
    }
}
