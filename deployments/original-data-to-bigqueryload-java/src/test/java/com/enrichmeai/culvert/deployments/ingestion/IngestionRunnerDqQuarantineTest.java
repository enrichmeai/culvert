package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The schema-level (as opposed to CSV-field-count) quarantine path through
 * {@link IngestionRunner}, for typed columns (#253).
 *
 * <p>A CSV cell is always text, and
 * {@link com.enrichmeai.culvert.dataquality.DataQualityTransform} checks INT64
 * and FLOAT64 fields against {@code Number} and BOOL against {@code Boolean}.
 * Before #253 that made every value in such a column a TYPE_MISMATCH, so the
 * {@code decision} and {@code applications} samples could not load a row with
 * a score or an amount. {@link CsvCellTypes} now reads those cells as numbers
 * and booleans first: a value that parses loads, one that does not is
 * quarantined naming it, and an empty cell is a missing value.
 */
class IngestionRunnerDqQuarantineTest {

    private static final String SOURCE_URI = "gs://landing/generic/decision/generic_decision_20260601.csv";
    private static final String TARGET_TABLE = "proj.odp_generic.decision";
    private static final String STAGING_PREFIX = "gs://staging-bucket/staging";
    private static final String ERROR_PREFIX = "gs://error-bucket/errors";
    private static final String CSV_HEADER =
            "decision_id,customer_id,application_id,decision_code,decision_date,score,reason_codes";

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
    void aNumericScoreLoadsAsANumber() {
        IngestionResult result = runDecision("run-dq-1", 1,
                "dec-1,cust-1,app-1,APPROVE,2026-06-01T00:00:00Z,720,");

        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(result.invalidRowCount()).isZero();
        assertThat(staged("decision", "run-dq-1")).contains("\"score\":720,");
        assertThat(quarantineUris("run-dq-1")).isEmpty();
    }

    @Test
    void aScoreThatIsNotANumberIsQuarantinedNamingTheValue() {
        IngestionResult result = runDecision("run-dq-2", 0,
                "dec-2,cust-1,app-1,APPROVE,2026-06-01T00:00:00Z,abc,");

        assertThat(result.validRowCount()).isZero();
        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(quarantined("run-dq-2"))
                .contains("\"field\":\"score\"")
                .contains("\"score\":\"abc\"")
                .contains("expected type compatible with INT64 (Number) but got String");
    }

    @Test
    void anEmptyOptionalScoreLoadsAsMissing() {
        IngestionResult result = runDecision("run-dq-3", 1,
                "dec-3,cust-1,app-1,APPROVE,2026-06-01T00:00:00Z,,");

        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(result.invalidRowCount()).isZero();
        assertThat(staged("decision", "run-dq-3")).contains("\"score\":null,");
    }

    @Test
    void theApplicationsSampleLoadsItsAmountsAndTerm() {
        String header = "application_id,customer_id,loan_amount,interest_rate,term_months,"
                + "application_date,status,event_type,account_type";
        String uri = "gs://landing/generic/applications/generic_applications_20260601.csv";
        blobStore.seed(uri, EnvelopeFixtures.buildFileBytes("Generic", "applications", "20260601", header,
                List.of("app-1,cust-1,25000.50,4.25,36,2026-05-30,SUBMITTED,,")));
        warehouse.returnRowCount(1);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-dq-4", "applications", uri, "20260601", "proj.odp_generic.applications"));

        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(staged("applications", "run-dq-4"))
                .contains("\"loan_amount\":25000.5,")
                .contains("\"interest_rate\":4.25,")
                .contains("\"term_months\":36,");
    }

    @Test
    void anEmptyRequiredNumberIsQuarantinedAsMissing() {
        IngestionResult result = runFromSchemaFile("run-dq-5", 0, "r-1,");

        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(quarantined("run-dq-5"))
                .contains("\"field\":\"amount\"")
                .contains("is REQUIRED but was null or absent");
    }

    @Test
    void aRangeOnANumericColumnIsNowEnforced() {
        IngestionResult result = runFromSchemaFile("run-dq-6", 1, "r-1,10", "r-2,1000");

        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(quarantined("run-dq-6")).contains("\"field\":\"amount\"").contains("1000");
        assertThat(staged("payments", "run-dq-6")).contains("\"amount\":10,").doesNotContain("1000");
    }

    @Test
    void aBooleanAndAnExponentLoadThroughASchemaFile() {
        String schema = """
                entity: flags
                headers: [flag_id, active, weight]
                fields:
                  - {name: flag_id, type: STRING, required: true}
                  - {name: active, type: BOOL}
                  - {name: weight, type: FLOAT64}
                """;
        String uri = "gs://landing/generic/flags/generic_flags_20260601.csv";
        blobStore.seed(uri, EnvelopeFixtures.buildFileBytes(
                "Generic", "flags", "20260601", "flag_id,active,weight",
                List.of("f-1,TRUE,1.5e3", "f-2,yes,1")));
        warehouse.returnRowCount(1);

        IngestionResult result = runner.run(new IngestionRequest("run-dq-7", "flags", uri, "20260601",
                "proj.odp_generic.flags", "flags.schema.yaml", schema));

        assertThat(result.validRowCount()).isEqualTo(1);
        assertThat(staged("flags", "run-dq-7")).contains("\"active\":true,").contains("\"weight\":1500.0,");
        assertThat(quarantined("run-dq-7")).contains("\"field\":\"active\"").contains("\"active\":\"yes\"");
    }

    @Test
    void aBlankRequiredStringIsQuarantinedAsMissing() {
        // #255: customers.ssn and customers.dob are required; a blank cell used to load as "".
        String header = "customer_id,first_name,last_name,ssn,dob,status,created_date";
        String uri = "gs://landing/generic/customers/generic_customers_20260601.csv";
        blobStore.seed(uri, EnvelopeFixtures.buildFileBytes("Generic", "customers", "20260601", header,
                List.of("c-1,Ada,Lovelace,,1815-12-10,A,2020-01-01",
                        "c-2,Alan,Turing,123-45-6789,  ,A,2020-01-01",
                        "c-3,Grace,Hopper,987-65-4321,1906-12-09,,")));
        warehouse.returnRowCount(1);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-dq-8", "customers", uri, "20260601", "proj.odp_generic.customers"));

        assertThat(result.validRowCount()).isEqualTo(1); // c-3: status and created_date are optional
        assertThat(result.invalidRowCount()).isEqualTo(2);
        assertThat(quarantined("run-dq-8"))
                .contains("\"field\":\"ssn\"")
                .contains("\"field\":\"dob\"")
                .contains("is REQUIRED but was null or absent");
        assertThat(staged("customers", "run-dq-8")).contains("\"customer_id\":\"c-3\"").contains("\"status\":\"\"");
    }

    private IngestionResult runDecision(String runId, long loaded, String... rows) {
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "decision", "20260601", CSV_HEADER, List.of(rows)));
        warehouse.returnRowCount(loaded);
        return runner.run(new IngestionRequest(runId, "decision", SOURCE_URI, "20260601", TARGET_TABLE));
    }

    private IngestionResult runFromSchemaFile(String runId, long loaded, String... rows) {
        String schema = """
                entity: payments
                headers: [payment_id, amount]
                fields:
                  - {name: payment_id, type: STRING, required: true}
                  - {name: amount, type: INT64, required: true, range: {min: 0, max: 500}}
                """;
        String uri = "gs://landing/generic/payments/generic_payments_20260601.csv";
        blobStore.seed(uri, EnvelopeFixtures.buildFileBytes(
                "Generic", "payments", "20260601", "payment_id,amount", List.of(rows)));
        warehouse.returnRowCount(loaded);
        return runner.run(new IngestionRequest(runId, "payments", uri, "20260601",
                "proj.odp_generic.payments", "payments.schema.yaml", schema));
    }

    private String staged(String entity, String runId) {
        return new String(blobStore.get(STAGING_PREFIX + "/" + entity + "/" + runId + ".ndjson"),
                StandardCharsets.UTF_8);
    }

    private List<String> quarantineUris(String runId) {
        return blobStore.writtenUris().stream().filter(u -> u.contains("/quarantine/" + runId + "/")).toList();
    }

    private String quarantined(String runId) {
        List<String> uris = quarantineUris(runId);
        assertThat(uris).hasSize(1);
        return new String(blobStore.get(uris.get(0)), StandardCharsets.UTF_8);
    }
}
