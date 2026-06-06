package com.enrichmeai.culvert.e2e.dq;

import com.enrichmeai.culvert.dataquality.DataQualityTransform;
import com.enrichmeai.culvert.dataquality.NumericRange;
import com.enrichmeai.culvert.dataquality.ValidationResult;
import com.enrichmeai.culvert.gcp.bigquery.RetryOrchestrator;
import com.enrichmeai.culvert.gcp.gcs.FailedRowRecord;
import com.enrichmeai.culvert.gcp.gcs.QuarantineHandler;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.MaskingStrategy;
import com.enrichmeai.culvert.governance.PiiMaskingGovernancePolicy;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Sprint-14 T14.5 (#82) — Data-quality / error-handling E2E slice.
 *
 * <p>This is the structural proof of the full DQ→quarantine path end-to-end:
 * <ol>
 *   <li>{@link DataQualityTransform} with a schema covering REQUIRED, typed
 *       (FLOAT64 with range), and PII-tagged fields validates a mixed row set.</li>
 *   <li>Valid rows receive PII masking via {@link PiiMaskingGovernancePolicy} before
 *       they exit the DQ stage.</li>
 *   <li>Invalid rows are adapted via {@link InvalidRowAdapter} and written to
 *       {@link QuarantineHandler} backed by an {@link InMemoryBlobStore};
 *       {@link StubJobControlRepository#markFailed} is called.</li>
 *   <li>{@link RetryOrchestrator} cleans up partial-load rows and proves that a
 *       re-run produces no duplicates.</li>
 *   <li>The {@link InvalidRowAdapter} seam round-trips: an
 *       {@link ValidationResult.InvalidRow} adapts to a {@link FailedRowRecord}
 *       carrying the identical row content and violations.</li>
 * </ol>
 *
 * <h2>Schema under test</h2>
 * <pre>
 *   caseRecord
 *     id       STRING  REQUIRED           — triggers MISSING_REQUIRED if absent
 *     score    FLOAT64 REQUIRED [0, 100]  — triggers OUT_OF_RANGE for score &gt; 100
 *     email    STRING  NULLABLE           — PII: masked to "***" on valid rows
 * </pre>
 *
 * <h2>Row type</h2>
 * <p>{@code R = Map<String,Object>} with {@code rowAccessor = Function.identity()}.
 * This makes the adapter's rowToMap trivial and the round-trip exact.
 *
 * <h2>Mutable-map note</h2>
 * <p>PII masking mutates the row map in place (documented in
 * {@link DataQualityTransform} javadoc). Test rows backing valid cases use
 * {@code new HashMap<>(...)} — NOT {@code Map.of(...)}.
 *
 * <h2>Live GCS / emulator</h2>
 * <p>No live GCP, no Docker. The live-emulator integration test is
 * {@link #liveGcsQuarantineIT_skeleton} ({@code @Disabled}); it will be enabled
 * in Sprint-15 T15.3 once the Testcontainers-based GCS emulator gate is green.
 *
 * <p>Sprint-14 / issue #82 (T14.5).
 */
class ReferenceE2EDqTest {

    // -----------------------------------------------------------------------
    // Schema: REQUIRED id, REQUIRED score [0,100], NULLABLE PII email
    // -----------------------------------------------------------------------

    /** The schema used across all tests in this class. */
    private static final EntitySchema CASE_SCHEMA = EntitySchema.of("caseRecord", List.of(
            SchemaField.required("id",    "STRING"),
            SchemaField.required("score", "FLOAT64").withRange(NumericRange.of(0.0, 100.0)),
            SchemaField.nullable("email", "STRING")
    ));

    // -----------------------------------------------------------------------
    // PII masking policy: email → FULL masking ("***")
    // -----------------------------------------------------------------------

    private static final PiiMaskingGovernancePolicy PII_POLICY =
            PiiMaskingGovernancePolicy.builder()
                    .piiColumns(Set.of("email"))
                    .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
                    .build();

    // -----------------------------------------------------------------------
    // Infrastructure stubs
    // -----------------------------------------------------------------------

    private InMemoryBlobStore blobStore;
    private StubJobControlRepository jobRepo;

    private static final String ERROR_PREFIX = "gs://culvert-errors-stub/errors/reference-e2e-gcp";
    private static final Clock FIXED_CLOCK =
            Clock.fixed(Instant.parse("2026-06-04T10:00:00.000Z"), ZoneOffset.UTC);

    @BeforeEach
    void setUp() {
        blobStore = new InMemoryBlobStore();
        jobRepo   = new StubJobControlRepository();
    }

    // -----------------------------------------------------------------------
    // Test 1: mixed-validity row set
    // -----------------------------------------------------------------------

    /**
     * Mixed-validity: valid rows reach the success path; invalid rows are written
     * to the quarantine stub and {@code markFailed} is called.
     *
     * <p>Row set:
     * <ul>
     *   <li>Row A — fully valid (id present, score in range, email present)</li>
     *   <li>Row B — missing required {@code id} field → MISSING_REQUIRED</li>
     *   <li>Row C — score 150.0 (> max 100.0) → OUT_OF_RANGE</li>
     * </ul>
     */
    @Test
    @DisplayName("mixed-validity: valid rows → success path; invalid rows → quarantine stub + markFailed called")
    void mixedValidityRowSet_validRowsSucceedInvalidRowsQuarantined() {
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(CASE_SCHEMA, Function.identity());

        // Valid row (mutable map — required by masking if policy were wired,
        // used here for consistency)
        Map<String, Object> rowA = new HashMap<>(Map.of(
                "id", "case-001", "score", 75.0, "email", "alice@example.com"));

        // Invalid: missing id
        Map<String, Object> rowB = new HashMap<>(Map.of(
                "score", 80.0, "email", "bob@example.com"));

        // Invalid: score out of range
        Map<String, Object> rowC = new HashMap<>(Map.of(
                "id", "case-003", "score", 150.0, "email", "carol@example.com"));

        List<Map<String, Object>> inputs = List.of(rowA, rowB, rowC);

        List<Map<String, Object>> validRows   = new ArrayList<>();
        List<ValidationResult.InvalidRow<Map<String, Object>>> invalidRows = new ArrayList<>();

        for (Map<String, Object> row : inputs) {
            ValidationResult<Map<String, Object>> result = dq.validate(row);
            if (result instanceof ValidationResult.ValidRow<Map<String, Object>> v) {
                validRows.add(v.row());
            } else if (result instanceof ValidationResult.InvalidRow<Map<String, Object>> inv) {
                invalidRows.add(inv);
            }
        }

        // --- success path: exactly 1 valid row ---
        assertThat(validRows)
                .as("Row A (valid) must reach the success path")
                .hasSize(1);
        assertThat(validRows.get(0)).containsEntry("id", "case-001");

        // --- invalid rows: 2 rows failed ---
        assertThat(invalidRows)
                .as("Rows B and C must be classified as invalid")
                .hasSize(2);

        // Row B: MISSING_REQUIRED violation on 'id'
        ValidationResult.InvalidRow<Map<String, Object>> invB = invalidRows.get(0);
        assertThat(invB.violations())
                .as("Row B must carry a MISSING_REQUIRED violation on 'id'")
                .anyMatch(v -> "id".equals(v.fieldName()));

        // Row C: OUT_OF_RANGE violation on 'score'
        ValidationResult.InvalidRow<Map<String, Object>> invC = invalidRows.get(1);
        assertThat(invC.violations())
                .as("Row C must carry an OUT_OF_RANGE violation on 'score'")
                .anyMatch(v -> "score".equals(v.fieldName()));

        // --- quarantine via adapter ---
        List<FailedRowRecord> records = InvalidRowAdapter.adaptAll(invalidRows, Function.identity());
        assertThat(records).hasSize(2);

        QuarantineHandler handler = new QuarantineHandler(
                blobStore, jobRepo, ERROR_PREFIX, FIXED_CLOCK);
        String runId = "run-s14-mixed";
        handler.writeFailures(runId, records);

        // BlobStore received exactly one quarantine file
        assertThat(blobStore.writtenUris())
                .as("QuarantineHandler must write exactly one JSONL file")
                .hasSize(1);
        assertThat(blobStore.writtenUris().get(0))
                .as("Quarantine URI must contain the runId")
                .contains(runId);

        // markFailed called once with DQ_VALIDATION_FAILURE
        assertThat(jobRepo.markFailedCalls)
                .as("markFailed must be called once")
                .hasSize(1);
        assertThat(jobRepo.markFailedCalls.get(0).errorCode())
                .isEqualTo(QuarantineHandler.ERROR_CODE);
        assertThat(jobRepo.markFailedCalls.get(0).errorFilePath())
                .isPresent()
                .hasValue(blobStore.writtenUris().get(0));
    }

    // -----------------------------------------------------------------------
    // Test 2: PII masking applied before a valid row exits the DQ stage
    // -----------------------------------------------------------------------

    /**
     * PII masking: a valid row has its {@code email} field masked to {@code "***"}
     * before it exits the DQ stage.
     *
     * <p>Masking requires a <em>mutable</em> map (HashMap, not Map.of) because
     * {@link DataQualityTransform} calls {@code entry.setValue(...)} in place.
     */
    @Test
    @DisplayName("PII masking applied to valid row's email field before it exits DQ stage")
    void piiMasking_appliedToValidRowBeforeExit() {
        // Wire DataQualityTransform WITH the PII masking policy
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(CASE_SCHEMA, Function.identity(), PII_POLICY);

        // Mutable map — masking mutates in place
        Map<String, Object> row = new HashMap<>(Map.of(
                "id", "case-pii-001", "score", 42.0, "email", "sensitive@example.com"));

        ValidationResult<Map<String, Object>> result = dq.validate(row);

        assertThat(result.isValid())
                .as("Row with valid id, score in range, and nullable email must be valid")
                .isTrue();

        // After validate() returns, masking has been applied to the row's email field
        assertThat(result.row())
                .as("Email field must be masked to '***' after DQ stage")
                .containsEntry("email", "***");

        assertThat(result.row())
                .as("Non-PII fields must be unchanged")
                .containsEntry("id",    "case-pii-001")
                .containsEntry("score", 42.0);
    }

    // -----------------------------------------------------------------------
    // Test 3: retry scenario — cleanupPartialLoad removes stale rows, re-run no duplicates
    // -----------------------------------------------------------------------

    /**
     * Retry: {@code cleanupPartialLoad} removes stale rows; re-run produces no
     * duplicates.
     *
     * <p>Scenario:
     * <ol>
     *   <li>Seed a {@link JobStatus#FAILED} job with target table + 2 partial-load rows.</li>
     *   <li>First {@code prepareRetry}: cleans up 2 rows, transitions to RETRYING,
     *       retryCount = 1.</li>
     *   <li>Target table is now empty → re-run inserts 2 rows afresh (no duplicates).</li>
     *   <li>Second {@code prepareRetry} on an already-RETRYING job: idempotent —
     *       counter stays at 1, rows not cleaned again.</li>
     * </ol>
     */
    @Test
    @DisplayName("retry: cleanupPartialLoad removes stale rows; re-run no duplicates (idempotency)")
    void retry_cleanupPartialLoad_rerunNoDuplicates() {
        String runId    = "run-s14-retry";
        String tableId  = "stub-project.staging.caseRecord";

        // Seed a FAILED job
        PipelineJob failedJob = PipelineJob.builder(
                runId, "system-s14", "case-ingest", LocalDate.of(2026, 6, 4),
                JobStatus.FAILED)
                .jobType(JobType.INGESTION)
                .targetTable(tableId)
                .retryCount(0)
                .build();
        jobRepo.seedJob(failedJob);

        // Simulate 2 partial-load rows already in the target table from the failed run
        jobRepo.insertTargetRow(runId);
        jobRepo.insertTargetRow(runId);
        assertThat(jobRepo.targetRowCount(runId)).isEqualTo(2);

        // First prepareRetry: cleanup + markRetrying
        RetryOrchestrator orchestrator = new RetryOrchestrator(jobRepo);
        RetryOrchestrator.RetryResult result1 = orchestrator.prepareRetry(runId);

        assertThat(result1.rowsCleaned())
                .as("First retry must clean the 2 partial-load rows")
                .isEqualTo(2);
        assertThat(result1.retryCount())
                .as("Retry counter must increment to 1")
                .isEqualTo(1);
        assertThat(jobRepo.targetRowCount(runId))
                .as("Target table must be empty after cleanup")
                .isEqualTo(0);

        // Simulate re-run: insert 2 rows again (no duplicates — table was clean)
        jobRepo.insertTargetRow(runId);
        jobRepo.insertTargetRow(runId);
        assertThat(jobRepo.targetRowCount(runId))
                .as("Re-run inserts exactly 2 rows (no duplicates from prior run)")
                .isEqualTo(2);

        // Second prepareRetry on an already-RETRYING job: idempotent
        RetryOrchestrator.RetryResult result2 = orchestrator.prepareRetry(runId);
        assertThat(result2.retryCount())
                .as("Idempotent: retry counter must remain at 1 for already-RETRYING job")
                .isEqualTo(1);
        assertThat(result2.rowsCleaned())
                .as("Idempotent path must report 0 rows cleaned (no cleanup ran)")
                .isEqualTo(0);
        assertThat(jobRepo.targetRowCount(runId))
                .as("Target-table rows must be untouched by the idempotent re-run path")
                .isEqualTo(2);
    }

    // -----------------------------------------------------------------------
    // Test 4: seam adapter — InvalidRow→FailedRowRecord round-trip
    // -----------------------------------------------------------------------

    /**
     * Seam-proof: {@link InvalidRowAdapter} adapts an
     * {@link ValidationResult.InvalidRow} to a {@link FailedRowRecord} that
     * carries the identical row content and violations.
     *
     * <h2>R-vs-serializable reconciliation</h2>
     * <p>{@code InvalidRow<R>} stores the row as generic {@code R}; it does
     * not itself expose a {@code Map}.  The adapter re-applies the same
     * {@code Function<R, Map<String,Object>>} accessor (here
     * {@code Function.identity()} since {@code R = Map}) to project the row.
     * {@code FailedRowRecord.rowContent()} then returns that map.
     *
     * <p>Violation mapping: {@link com.enrichmeai.culvert.dataquality.FieldViolation#fieldName()}
     * → {@link FailedRowRecord.ViolationDescriptor#field()} and
     * {@link com.enrichmeai.culvert.dataquality.FieldViolation#detail()}
     * → {@link FailedRowRecord.ViolationDescriptor#rule()}.
     * ({@code violationKind} is the structural category; the seam interface
     * surfaces the human-readable rule message instead.)
     */
    @Test
    @DisplayName("seam adapter: InvalidRow<Map> → FailedRowRecord compiles + round-trips")
    void seamAdapter_invalidRowAdaptsToFailedRowRecord_roundTrip() {
        // Construct an InvalidRow via DataQualityTransform (uses the real DQ engine)
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(CASE_SCHEMA, Function.identity());

        // Missing 'id' (MISSING_REQUIRED) + score out-of-range (OUT_OF_RANGE)
        Map<String, Object> rawRow = new HashMap<>(Map.of(
                "score", 999.0, "email", "test@example.com"));

        ValidationResult<Map<String, Object>> result = dq.validate(rawRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalidRow =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;

        // ---- ADAPT ----
        FailedRowRecord adapted = InvalidRowAdapter.adapt(invalidRow, Function.identity());

        // --- rowContent round-trip: same entries as the original map ---
        assertThat(adapted.rowContent())
                .as("rowContent() must carry the same entries as the original row")
                .containsEntry("score", 999.0)
                .containsEntry("email", "test@example.com")
                .doesNotContainKey("id");   // id was absent from the input

        // --- violations round-trip ---
        assertThat(adapted.violations())
                .as("Adapted violations must cover all FieldViolations from the InvalidRow")
                .hasSameSizeAs(invalidRow.violations());

        // Verify each adapted violation maps fieldName+detail correctly
        for (int i = 0; i < invalidRow.violations().size(); i++) {
            var original = invalidRow.violations().get(i);
            var descriptor = adapted.violations().get(i);
            assertThat(descriptor.field())
                    .as("field() must equal FieldViolation.fieldName()")
                    .isEqualTo(original.fieldName());
            assertThat(descriptor.rule())
                    .as("rule() must equal FieldViolation.detail()")
                    .isEqualTo(original.detail());
        }

        // Specific violations expected
        assertThat(adapted.violations())
                .as("Adapter must carry MISSING_REQUIRED violation on 'id'")
                .anyMatch(v -> "id".equals(v.field()));
        assertThat(adapted.violations())
                .as("Adapter must carry OUT_OF_RANGE violation on 'score'")
                .anyMatch(v -> "score".equals(v.field()));
    }

    // -----------------------------------------------------------------------
    // @Disabled integration skeleton — live GCS emulator path
    // -----------------------------------------------------------------------

    /**
     * Live-GCS integration skeleton.
     *
     * <p><strong>Run manually</strong> once the Testcontainers-based GCS emulator
     * integration test ({@code GcsBlobStoreIT}) is green in
     * {@code data-pipeline-gcp-gcs-java}. This test is gated in Sprint-15 T15.3:
     *
     * <pre>
     *   # Start the fake-gcs-server container (requires Docker):
     *   docker run -p 4443:4443 fsouza/fake-gcs-server -scheme http
     *
     *   # Run with the IT profile:
     *   mvn -P it verify -pl deployments/reference-e2e-gcp
     * </pre>
     *
     * <p>When enabled, replace {@link InMemoryBlobStore} with the real
     * {@code GcsBlobStore} pointing at the fake-gcs-server endpoint, and replace
     * {@link StubJobControlRepository} with the real BigQuery-backed repository
     * (or the BigQuery emulator equivalent from {@code data-pipeline-it-support}).
     *
     * <p>Live GCS URI pattern:
     * <pre>
     *   gs://&lt;error-bucket&gt;/errors/reference-e2e-gcp/quarantine/&lt;runId&gt;/&lt;ts&gt;.jsonl
     * </pre>
     */
    @Test
    @Disabled("Sprint-15 T15.3: enable once GcsBlobStoreIT + BigQuery emulator are green in CI")
    void liveGcsQuarantineIT_skeleton() {
        // TODO (Sprint-15 T15.3):
        //   1. Spin up fake-gcs-server via Testcontainers (FakeGcsServerContainer from
        //      data-pipeline-it-support).
        //   2. Instantiate GcsBlobStore pointing at the fake-gcs server.
        //   3. Spin up BigQuery emulator and create a job_control table.
        //   4. Run the same DQ pipeline scenario from mixedValidityRowSet_... but
        //      with the real BlobStore and real/emulator JobControlRepository.
        //   5. Assert the quarantine file exists in GCS (gs://... URI).
        //   6. Assert markFailed wrote the correct errorFilePath to the job-control table.
        throw new AssertionError("Live-GCS IT skeleton — must not reach here while @Disabled");
    }
}
