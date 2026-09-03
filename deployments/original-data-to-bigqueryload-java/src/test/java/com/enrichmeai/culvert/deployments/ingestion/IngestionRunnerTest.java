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

        // The TRL declares 2 records: 1 loaded + 1 quarantined = 2 accounted for,
        // so this RECONCILES. Reconciliation asks "did every declared record land
        // somewhere?", not "did every declared record load" — a quarantined row
        // has not vanished, it is sitting in the error bucket where an operator
        // can read it. Counting only loaded rows would make every use of the
        // quarantine path a reconciliation failure, which would mean the pipeline
        // aborts precisely when it uses the mechanism built for not aborting.
        assertThat(result.reconciliation().isReconciled()).isTrue();
        assertThat(result.reconciliation().expectedCount()).isEqualTo(2);
        assertThat(result.reconciliation().accountedCount()).isEqualTo(2);

        // Quarantine file was written.
        assertThat(blobStore.writtenUris()).anyMatch(uri -> uri.contains("/quarantine/run-2/"));

        // One markFailed, from QuarantineHandler recording the quarantined row.
        // No RECONCILIATION_MISMATCH: nothing went missing.
        assertThat(jobControlRepository.markFailedCalls).hasSize(1);
        assertThat(jobControlRepository.markFailedCalls.get(0).errorCode())
                .isEqualTo("DQ_VALIDATION_FAILURE");
        assertThat(jobControlRepository.markFailedCalls.get(0).failureStage())
                .isEqualTo(FailureStage.VALIDATION);

        // Overall job succeeds — invalid rows are quarantined, not fatal.
        //
        // Note this run calls markFailed (the quarantine record) and then
        // updateStatus(SUCCEEDED). That is the same write-ordering shape as the
        // reconciliation bug, but here it is intended: the markFailed row is a
        // per-row quarantine note, not a verdict on the run. Under an append-only
        // job-control log (external review finding #4) both become visible events
        // rather than one overwriting the other.
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

    /**
     * Regression test for external review finding #1.
     *
     * <p>This method previously asserted the opposite — that a mismatch was
     * recorded and the run still ended SUCCEEDED, mirroring the Python
     * reference's reconciliation warning. That behaviour meant an
     * {@code UPDATE … SET status} overwrote the failure that had just been
     * written, so a load that did not reconcile reported green in the one place
     * an operator would look. Parity with a permissive reference is not a
     * reason to report a bad load as a good one.
     *
     * <p>Deliberately asserted against the CURRENT mutating
     * {@link RecordingJobControlRepository}: the fix is in the runner's control
     * flow, so it must hold regardless of whether job control is later made
     * append-only. An append-only store alone would NOT fix this — SUCCEEDED
     * appended after the failure still wins a newest-row-per-key read.
     */
    @Test
    void loadCountMismatch_failsTheRunAndNeverReportsSucceeded() {
        List<String> rows = List.of("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01");
        seedSourceFile(rows);
        // The row parses and validates fine, so accounting reconciles — but the
        // warehouse claims to have loaded 0 of the 1 row it was handed.
        warehouse.returnRowCount(0);

        assertThatThrownBy(() -> runner.run(new IngestionRequest(
                "run-4", "customers", SOURCE_URI, "20260601", TARGET_TABLE)))
                .isInstanceOf(ReconciliationMismatchException.class)
                .hasMessageContaining("staged 0");

        assertThat(jobControlRepository.markFailedCalls)
                .anyMatch(c -> c.errorCode().equals("LOAD_COUNT_MISMATCH")
                        && c.failureStage() == FailureStage.LOAD);

        // The point of the whole finding: SUCCEEDED must never be written.
        assertThat(jobControlRepository.statusUpdates).extracting(
                RecordingJobControlRepository.StatusUpdate::status)
                .containsExactly(JobStatus.RUNNING)
                .doesNotContain(JobStatus.SUCCEEDED);
    }

    /**
     * The other half of finding #1: records that vanish during parsing — counted
     * by the trailer, but neither loaded nor quarantined — must abort BEFORE the
     * target table is written (finding #3, reconcile before commit).
     *
     * <p>A data line identical to the CSV header is skipped by
     * {@link CsvRowParser} as a repeated header, so the trailer counts it and
     * nothing else ever sees it. That is a silent drop, and it is exactly what
     * the accounting check exists to catch.
     */
    @Test
    void unaccountedRecords_abortBeforeTheTargetIsWritten() {
        List<String> rows = List.of(
                "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
                CSV_HEADER); // counted by the TRL, silently skipped by the parser
        seedSourceFile(rows);

        assertThatThrownBy(() -> runner.run(new IngestionRequest(
                "run-4b", "customers", SOURCE_URI, "20260601", TARGET_TABLE)))
                .isInstanceOf(ReconciliationMismatchException.class)
                .hasMessageContaining("target table was NOT written");

        assertThat(jobControlRepository.markFailedCalls)
                .anyMatch(c -> c.errorCode().equals("RECONCILIATION_MISMATCH")
                        && c.failureStage() == FailureStage.RECONCILIATION);

        // Reconcile-before-commit: nothing was handed to the warehouse at all.
        assertThat(warehouse.loadCalls).isEmpty();

        assertThat(jobControlRepository.statusUpdates).extracting(
                RecordingJobControlRepository.StatusUpdate::status)
                .doesNotContain(JobStatus.SUCCEEDED);
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
