package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.LoadOptions;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.dataquality.DataQualityTransform;
import com.enrichmeai.culvert.dataquality.ValidationResult;
import com.enrichmeai.culvert.deployments.ingestion.envelope.EnvelopeParseException;
import com.enrichmeai.culvert.deployments.ingestion.envelope.EnvelopeParser;
import com.enrichmeai.culvert.deployments.ingestion.envelope.ParsedEnvelope;
import com.enrichmeai.culvert.deployments.ingestion.schema.GenericEntities;
import com.enrichmeai.culvert.gcp.gcs.FailedRowRecord;
import com.enrichmeai.culvert.gcp.gcs.QuarantineHandler;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Function;

/**
 * Orchestrates the full GCS-to-BigQuery ingestion flow for one Generic entity
 * file, end to end, in a single JVM call.
 *
 * <h2>Why this is one class, not a chain of {@code PipelineStage}s wired
 * through Beam PCollections</h2>
 * <p>Culvert's {@link com.enrichmeai.culvert.contracts.PipelineStage#execute}
 * is {@code void} and side-effecting: {@code StageTransform} (see
 * {@code data-pipeline-gcp-dataflow-java/.../StageTransform.java:20-38}) wraps
 * each stage as an independent {@code PBegin -> PDone} root triggered exactly
 * once — there is no element-level {@code PCollection} handoff between stages
 * yet ({@code DataflowPipeline.buildBeam} Javadoc,
 * {@code data-pipeline-gcp-dataflow-java/.../DataflowPipeline.java:179-193}:
 * "Richer element-level data flow... is the anchor for a future sprint").
 * A naive {@code ParseStage -> ValidateStage -> LoadStage -> ReconcileStage}
 * split would therefore not actually pass data between stages on a real
 * runner, and would look green on DirectRunner while doing nothing.
 *
 * <p>This class instead performs the whole read -> parse-envelope -> parse-CSV
 * -> validate -> stage-valid-rows -> bulk-load -> quarantine-invalid ->
 * reconcile -> job-control sequence directly, using the {@link BlobStore},
 * {@link Warehouse}, and {@link JobControlRepository} adapters resolved from a
 * {@link com.enrichmeai.culvert.contracts.RuntimeContext}. {@link IngestionStage}
 * wraps one call to this class as a single {@code PipelineStage}, and
 * {@link com.enrichmeai.culvert.deployments.ingestion.IngestionMain} still
 * builds a {@link com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline} around
 * it — so the deployment gets a real, validated Culvert DAG/topology artifact
 * (one stage today), without pretending stages hand off rows through Beam.
 *
 * <h2>Flow (ports the Python reference pipeline)</h2>
 * <ol>
 *   <li>Read the source file's bytes from {@link BlobStore} (mirrors
 *       {@code runner.py}'s {@code MatchFiles/ReadMatches/ReadContent}).</li>
 *   <li>Split into lines and parse the HDR/TRL envelope via {@link EnvelopeParser}
 *       (mirrors {@code ValidateFileDoFn} + {@code GenericFileValidator}).</li>
 *   <li>Parse each CSV data line into a field map via {@link CsvRowParser}
 *       (mirrors {@code ParseAndValidateRecordDoFn}'s CSV split).</li>
 *   <li>Schema-validate each row via {@link DataQualityTransform} (mirrors
 *       {@code SchemaValidator} / {@code GenericRecordValidator}).</li>
 *   <li>Quarantine invalid rows (parse errors + schema violations) via
 *       {@link QuarantineHandler#writeFailures} (mirrors the Python error-table
 *       write, but via Culvert's dead-letter convention instead of a BigQuery
 *       error table).</li>
 *   <li><strong>Reconcile before commit</strong> — declared count vs.
 *       loaded-plus-quarantined. Abort here and the target table is untouched.</li>
 *   <li>Serialise valid rows as newline-delimited JSON to a staging blob,
 *       delete any rows a previous run of the same extract date left behind,
 *       then bulk-load via {@link Warehouse#loadFromUri} (replaces the Python
 *       {@code WriteToBigQuery(method='STREAMING_INSERTS')} path).</li>
 *   <li>Check load integrity — staged rows vs. rows the warehouse says it took.</li>
 *   <li>Create/update the job-control record throughout (mirrors
 *       {@code JobControlRepository.create_job/update_status/mark_failed}).</li>
 * </ol>
 *
 * <h2>Two reconciliation checks, and why both must be terminal</h2>
 * <p>Step 6 compares the envelope's declared count against what this run could
 * account for — rows loaded plus rows quarantined (see
 * {@link ReconciliationResult}). It runs <em>before</em> the target is written,
 * so a source file whose records do not add up never half-lands.
 *
 * <p>Step 8 compares the rows handed to the warehouse against the count the
 * warehouse reports back. These catch different faults and neither subsumes
 * the other: a warehouse that silently drops rows sails through step 6.
 *
 * <p>Both throw {@link ReconciliationMismatchException}. They used to do
 * neither — the mismatch was recorded with {@code markFailed} and then
 * overwritten by {@code updateStatus(SUCCEEDED)} on the way out, so a load
 * that did not reconcile ended green. See that exception's Javadoc.
 *
 * <h2>Re-running the same extract</h2>
 * <p>Loading is idempotent per extract date: the run deletes anything a
 * previous attempt at that {@code _extract_date} wrote before appending, so
 * running the same extract twice leaves one copy of the data rather than two.
 * {@link LoadOptions} makes the disposition explicit at the call site — the
 * absence of one is what made the duplication silent.
 */
public final class IngestionRunner {

    private static final Gson GSON = new GsonBuilder().serializeNulls().create();
    private static final DateTimeFormatter EXTRACT_DATE_FMT = DateTimeFormatter.BASIC_ISO_DATE;

    private final BlobStore blobStore;
    private final Warehouse warehouse;
    private final JobControlRepository jobControlRepository;
    private final String stagingPathPrefix;
    private final String errorPathPrefix;

    /**
     * @param blobStore            Source-file + staging-file storage.
     * @param warehouse            BigQuery (or equivalent) warehouse for the bulk load.
     * @param jobControlRepository Job-control ledger.
     * @param stagingPathPrefix    URI prefix (no trailing slash) under which this runner
     *                             writes a temporary NDJSON staging file before
     *                             {@code loadFromUri}, e.g. {@code gs://my-bucket/staging}.
     * @param errorPathPrefix      URI prefix (no trailing slash) passed to
     *                             {@link QuarantineHandler}, e.g. {@code gs://my-bucket/errors}.
     */
    public IngestionRunner(
            BlobStore blobStore,
            Warehouse warehouse,
            JobControlRepository jobControlRepository,
            String stagingPathPrefix,
            String errorPathPrefix) {
        this.blobStore = Objects.requireNonNull(blobStore, "blobStore must not be null");
        this.warehouse = Objects.requireNonNull(warehouse, "warehouse must not be null");
        this.jobControlRepository =
                Objects.requireNonNull(jobControlRepository, "jobControlRepository must not be null");
        this.stagingPathPrefix = normalise(stagingPathPrefix);
        this.errorPathPrefix = normalise(errorPathPrefix);
    }

    /**
     * Run the full ingestion flow for one file.
     *
     * @param request Everything needed to process one entity file.
     * @return The outcome, including reconciliation result and row counts.
     */
    public IngestionResult run(IngestionRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        String runId = request.runId();
        String entity = request.entity();

        if (!GenericEntities.isKnownEntity(entity)) {
            throw new IllegalArgumentException("Unknown entity: " + entity);
        }

        LocalDate extractDate = parseExtractDate(request.extractDate());
        PipelineJob job = PipelineJob.builder(runId, GenericEntities.SYSTEM_ID,
                        "generic_" + entity + "_load", extractDate, JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType(entity)
                .sourceFile(request.sourceUri())
                .targetTable(request.targetTable())
                .build();
        jobControlRepository.createJob(job);
        jobControlRepository.updateStatus(runId, JobStatus.RUNNING, Optional.empty());

        try {
            IngestionResult result = process(request);
            jobControlRepository.updateStatus(runId, JobStatus.SUCCEEDED,
                    Optional.of(result.loadedRowCount()));
            return result;
        } catch (ReconciliationMismatchException e) {
            // process() has already recorded the mismatch with its specific
            // error code and stage. Re-marking here would replace that detail
            // with a vaguer PIPELINE_FAILED, and falling through to the generic
            // handler below is exactly how the original bug read as harmless.
            // Rethrow untouched: the run is over, and it is not a success.
            throw e;
        } catch (EnvelopeParseException e) {
            jobControlRepository.markFailed(runId, "ENVELOPE_VALIDATION_FAILURE", e.getMessage(),
                    FailureStage.VALIDATION, Optional.empty());
            throw e;
        } catch (RuntimeException e) {
            jobControlRepository.markFailed(runId, "PIPELINE_FAILED",
                    truncate(String.valueOf(e.getMessage()), 500),
                    FailureStage.UNKNOWN, Optional.empty());
            throw e;
        }
    }

    private IngestionResult process(IngestionRequest request) {
        String runId = request.runId();
        String entity = request.entity();
        EntitySchema schema = GenericEntities.schemaFor(entity);
        List<String> headers = GenericEntities.headersFor(entity);

        // 1. Read source file.
        byte[] content = blobStore.get(request.sourceUri());
        List<String> lines = splitLines(new String(content, StandardCharsets.UTF_8));

        // 2. Parse + validate the HDR/TRL envelope.
        EnvelopeParser envelopeParser = EnvelopeParser.withCsvHeaderRow();
        ParsedEnvelope envelope = envelopeParser.parse(lines, GenericEntities.SYSTEM_ID, entity);

        // 3. Parse CSV data lines (skip the leading CSV header row, mirrors
        //    ParseAndValidateRecordDoFn.process skipping a line that matches headers).
        CsvRowParser rowParser = new CsvRowParser(headers);
        List<Map<String, Object>> parseErrors = new ArrayList<>();
        List<Map<String, Object>> candidateRows = new ArrayList<>();

        for (String dataLine : envelope.dataLines()) {
            Optional<CsvRowParser.ParsedRow> parsed = rowParser.parseLine(dataLine);
            if (parsed.isEmpty()) {
                continue; // blank line or duplicate CSV header row
            }
            CsvRowParser.ParsedRow row = parsed.get();
            if (row.isError()) {
                Map<String, Object> errRecord = new LinkedHashMap<>();
                errRecord.put("line", row.rawLine());
                errRecord.put("error", row.error());
                parseErrors.add(errRecord);
            } else {
                candidateRows.add(row.fields());
            }
        }

        // 4. Schema-validate each candidate row.
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, Function.identity());

        List<Map<String, Object>> validRows = new ArrayList<>();
        List<ValidationResult.InvalidRow<Map<String, Object>>> invalidRows = new ArrayList<>();
        for (Map<String, Object> candidate : candidateRows) {
            ValidationResult<Map<String, Object>> result = dq.validate(candidate);
            if (result instanceof ValidationResult.ValidRow<Map<String, Object>> v) {
                validRows.add(v.row());
            } else if (result instanceof ValidationResult.InvalidRow<Map<String, Object>> inv) {
                invalidRows.add(inv);
            }
        }

        // 5. Quarantine invalid rows (schema violations + CSV parse errors)
        //    BEFORE the target is touched. Quarantining is not a commit — it
        //    writes to the error bucket, never to the target table — and doing
        //    it first means a run that is about to abort still leaves the
        //    operator the evidence of WHY the counts did not add up.
        int quarantinedCount = invalidRows.size() + parseErrors.size();
        List<FailedRowRecord> quarantineRecords = new ArrayList<>(
                InvalidRowAdapter.adaptAll(invalidRows, Function.identity()));
        quarantineRecords.addAll(parseErrorsToFailedRowRecords(parseErrors));

        if (!quarantineRecords.isEmpty()) {
            QuarantineHandler quarantineHandler =
                    new QuarantineHandler(blobStore, jobControlRepository, errorPathPrefix);
            quarantineHandler.writeFailures(runId, quarantineRecords);
        }

        // 6. RECONCILE BEFORE COMMIT — is every declared record accounted for?
        //    Loaded-or-quarantined is the test; see ReconciliationResult for
        //    why quarantined rows count. A shortfall here means records went
        //    missing during parsing without landing anywhere, so we abort with
        //    the target table untouched rather than half-loading it and
        //    discovering the problem afterwards with no way back.
        ReconciliationResult accounting = new ReconciliationResult(
                envelope.trailer().recordCount(), (long) validRows.size() + quarantinedCount);
        if (!accounting.isReconciled()) {
            jobControlRepository.markFailed(runId, "RECONCILIATION_MISMATCH",
                    "Envelope declared " + accounting.expectedCount() + " records but only "
                            + accounting.accountedCount() + " were accounted for ("
                            + validRows.size() + " valid, " + quarantinedCount
                            + " quarantined). Target table not written.",
                    FailureStage.RECONCILIATION, Optional.empty());
            throw new ReconciliationMismatchException(accounting);
        }

        // 7. Stage valid rows to NDJSON and bulk-load — with the audit columns
        // the downstream dbt models contract on. The Python reference injects
        // these via AddAuditColumnsDoFn (transforms.py:107); the FDP
        // staging/join models read _run_id/_extract_date/_processed_at, so
        // omitting them loads rows that silently never join (caught by the
        // first real e2e on GCP, 2026-07-10).
        long loadedCount = 0L;
        String extractDateIso = java.time.LocalDate.parse(
                request.extractDate(), java.time.format.DateTimeFormatter.BASIC_ISO_DATE).toString();
        if (!validRows.isEmpty()) {
            String processedAt = java.time.Instant.now().toString();
            for (Map<String, Object> row : validRows) {
                row.put("_run_id", runId);
                row.put("_extract_date", extractDateIso);
                row.put("_processed_at", processedAt);
            }
            EntitySchema auditedSchema = withAuditColumns(schema);
            String stagingUri = stagingPathPrefix + "/" + entity + "/" + runId + ".ndjson";
            blobStore.put(stagingUri, toNdjson(validRows));

            // Make the load idempotent: drop anything a previous attempt at
            // THIS extract date already wrote, then append.
            //
            // Why delete-then-append rather than LoadOptions.truncatePartition:
            // the ODP tables are partitioned on BUSINESS dates (customers on
            // created_date, accounts on open_date -
            // scripts/gcp/03_create_infrastructure.sh:117-129), not on
            // _extract_date. One extract spans many business-date partitions,
            // so there is no single partition that means "this extract" and a
            // partition-scoped TRUNCATE cannot express the intent. A whole-table
            // TRUNCATE would be worse - it would delete every other extract.
            deletePriorLoadForExtract(request.targetTable(), extractDateIso);
            loadedCount = warehouse.loadFromUri(stagingUri, request.targetTable(), auditedSchema,
                    LoadOptions.append());
        }

        // 8. Post-load integrity: did the warehouse load everything we staged?
        //    Distinct from step 6 and NOT redundant with it - step 6 checks the
        //    source file against what we parsed, this checks what we handed the
        //    warehouse against what it says it took. A load that silently drops
        //    rows passes step 6 and fails here, and without this check it would
        //    still end SUCCEEDED - the original bug, moved one step later.
        ReconciliationResult loadIntegrity =
                new ReconciliationResult(validRows.size(), loadedCount);
        if (!loadIntegrity.isReconciled()) {
            jobControlRepository.markFailed(runId, "LOAD_COUNT_MISMATCH",
                    "Staged " + validRows.size() + " rows but the warehouse reported loading "
                            + loadedCount + ".",
                    FailureStage.LOAD, Optional.empty());
            throw new ReconciliationMismatchException(loadIntegrity);
        }

        return new IngestionResult(
                runId, entity, candidateRows.size(), validRows.size(),
                quarantinedCount, loadedCount, accounting);
    }

    /**
     * Remove rows a previous run of the same extract date already wrote, so a
     * re-run replaces rather than duplicates.
     *
     * <p>Keyed on {@code _extract_date} rather than {@code _run_id}: a retry
     * gets a fresh {@code runId}, so deleting by run id would leave the failed
     * attempt's rows in place and the retry would append a second copy - the
     * exact duplication this exists to prevent.
     *
     * <p>Issued through {@link com.enrichmeai.culvert.contracts.Warehouse#execute}
     * as plain parameterised SQL, so it stays within the cloud-neutral contract.
     *
     * <p><strong>Honest limitation — this delete and the load that follows are
     * not atomic.</strong> They are two separate warehouse jobs, so a crash
     * between them leaves the target missing the previous attempt's rows and
     * not yet holding the new ones. That window is a deliberate trade: before
     * this, the same crash left duplicated rows instead, and duplication is
     * both harder to detect and harder to undo than a gap. Re-running the
     * extract heals it, and the run is not marked SUCCEEDED, so job control
     * shows the hole rather than hiding it.
     *
     * <p>Closing the window properly means loading to a staging table,
     * reconciling there, and swapping in one BigQuery multi-statement
     * transaction — the shape the external review preferred. That was not done
     * here, and no test can catch its absence: {@code InMemoryTableWarehouse}
     * applies both statements in one process, so the gap is invisible to the
     * suite by construction.
     */
    private void deletePriorLoadForExtract(String targetTable, String extractDateIso) {
        warehouse.execute(
                "DELETE FROM " + targetTable + " WHERE _extract_date = @extract_date",
                Map.of("extract_date", extractDateIso));
    }

    private static List<FailedRowRecord> parseErrorsToFailedRowRecords(List<Map<String, Object>> parseErrors) {
        List<FailedRowRecord> out = new ArrayList<>(parseErrors.size());
        for (Map<String, Object> err : parseErrors) {
            out.add(new ParseErrorFailedRowRecord(err));
        }
        return out;
    }

    private static byte[] toNdjson(List<Map<String, Object>> rows) {
        StringBuilder sb = new StringBuilder();
        for (Map<String, Object> row : rows) {
            sb.append(GSON.toJson(row)).append('\n');
        }
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * The entity schema plus the audit columns every ODP row carries
     * ({@code _run_id}, {@code _extract_date}, {@code _processed_at}) — the
     * downstream dbt staging/FDP models join and filter on these, mirroring
     * the Python reference's {@code AddAuditColumnsDoFn}.
     */
    private static EntitySchema withAuditColumns(EntitySchema schema) {
        List<com.enrichmeai.culvert.schema.SchemaField> fields = new ArrayList<>(schema.fields());
        fields.add(com.enrichmeai.culvert.schema.SchemaField.nullable("_run_id", "STRING"));
        fields.add(com.enrichmeai.culvert.schema.SchemaField.nullable("_extract_date", "DATE"));
        fields.add(com.enrichmeai.culvert.schema.SchemaField.nullable("_processed_at", "TIMESTAMP"));
        return EntitySchema.of(schema.name(), fields);
    }

    private static List<String> splitLines(String content) {
        List<String> lines = new ArrayList<>(List.of(content.split("\n", -1)));
        lines.removeIf(String::isBlank);
        return lines;
    }

    private static LocalDate parseExtractDate(String yyyymmdd) {
        try {
            return LocalDate.parse(yyyymmdd, EXTRACT_DATE_FMT);
        } catch (RuntimeException e) {
            return LocalDate.now();
        }
    }

    private static String normalise(String prefix) {
        Objects.requireNonNull(prefix, "prefix must not be null");
        return prefix.endsWith("/") ? prefix.substring(0, prefix.length() - 1) : prefix;
    }

    private static String truncate(String s, int max) {
        return s.length() > max ? s.substring(0, max) : s;
    }

    /** {@link FailedRowRecord} for a row that failed CSV field-count parsing (not schema validation). */
    private record ParseErrorFailedRowRecord(Map<String, Object> rowContent) implements FailedRowRecord {
        @Override
        public List<? extends ViolationDescriptor> violations() {
            return List.of(new ParseViolation(String.valueOf(rowContent.get("error"))));
        }

        private record ParseViolation(String rule) implements ViolationDescriptor {
            @Override
            public String field() {
                return "_row";
            }
        }
    }
}
