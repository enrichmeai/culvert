package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Exercises the schema-level (as opposed to CSV-field-count) quarantine path
 * through {@link IngestionRunner}, using the {@code decision} entity.
 *
 * <h2>Why {@code decision} and not {@code customers}</h2>
 * <p>{@link com.enrichmeai.culvert.deployments.ingestion.schema.GenericEntities}'s
 * {@code decision} schema declares {@code score} as {@code INT64} (see
 * {@code GenericEntities.DECISION_SCHEMA}), and
 * {@link com.enrichmeai.culvert.dataquality.DataQualityTransform} type-checks
 * INT64 fields against {@code Number.class} (see
 * {@code DataQualityTransform.WIRE_TYPE_MAP}). Every value produced by
 * {@link CsvRowParser} is a raw {@code String} (CSV has no native typing), so
 * <strong>any non-empty {@code score} value on a CSV-sourced {@code decision}
 * row is unconditionally a TYPE_MISMATCH</strong> — this is a genuine fidelity
 * gap versus the Python reference (whose {@code SchemaValidator} coerces/validates
 * string-typed CSV cells against declared types rather than doing a raw
 * {@code isInstance} check), not a bug in this port. See the deployment
 * README "Known gaps vs the Python reference" section.
 *
 * <p>This test documents the gap by asserting the (perhaps surprising) actual
 * behaviour: a numeric-looking CSV value in an INT64-typed field is quarantined.
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
    void csvStringScoreIsAlwaysQuarantinedAsTypeMismatch() {
        List<String> rows = List.of(
                "dec-1,cust-1,app-1,APPROVE,2026-06-01T00:00:00Z,720,");
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "decision", "20260601", CSV_HEADER, rows));
        warehouse.returnRowCount(0);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-dq-1", "decision", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.candidateRowCount()).isEqualTo(1);
        // Documents the gap: the row is quarantined even though "720" is a
        // perfectly valid decision score, because DataQualityTransform sees a
        // String where it expects a Number.
        assertThat(result.validRowCount()).isZero();
        assertThat(result.invalidRowCount()).isEqualTo(1);
        assertThat(blobStore.writtenUris()).anyMatch(uri -> uri.contains("/quarantine/run-dq-1/"));

        String quarantineUri = blobStore.writtenUris().stream()
                .filter(uri -> uri.contains("/quarantine/run-dq-1/"))
                .findFirst()
                .orElseThrow();
        String quarantined = new String(blobStore.get(quarantineUri), java.nio.charset.StandardCharsets.UTF_8);
        assertThat(quarantined)
                .contains("\"field\":\"score\"")
                .contains("expected type compatible with INT64");
    }

    @Test
    void emptyScoreFieldIsAlsoQuarantinedBecauseCsvNeverProducesJavaNull() {
        // score is NULLABLE (not required); CsvRowParser fills a trailing-empty CSV
        // field with "" (empty string), never Java `null`. Because "" is a String
        // (not null), MISSING_REQUIRED does not fire (score isn't required anyway,
        // and the value isn't null) — but TYPE_MISMATCH DOES fire, since "" is still
        // a String, not a Number. This proves the gap applies even to an
        // intentionally-blank optional numeric field, not just populated ones.
        List<String> rows = List.of("dec-2,cust-1,app-1,APPROVE,2026-06-01T00:00:00Z,,");
        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "decision", "20260601", CSV_HEADER, rows));
        warehouse.returnRowCount(0);

        IngestionResult result = runner.run(new IngestionRequest(
                "run-dq-2", "decision", SOURCE_URI, "20260601", TARGET_TABLE));

        assertThat(result.invalidRowCount()).isEqualTo(1);
    }
}
