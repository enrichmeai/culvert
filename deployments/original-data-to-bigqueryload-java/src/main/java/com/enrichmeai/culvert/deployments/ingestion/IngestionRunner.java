package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
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
 *   <li>Serialise valid rows as newline-delimited JSON to a staging blob, then
 *       bulk-load via {@link Warehouse#loadFromUri} (replaces the Python
 *       {@code WriteToBigQuery(method='STREAMING_INSERTS')} path — see
 *       {@code BigQueryWarehouse.loadFromUri},
 *       {@code data-pipeline-gcp-bigquery-java/.../BigQueryWarehouse.java:128-147}).</li>
 *   <li>Quarantine invalid rows (parse errors + schema violations) via
 *       {@link QuarantineHandler#writeFailures} (mirrors the Python error-table
 *       write, but via Culvert's dead-letter convention instead of a BigQuery
 *       error table).</li>
 *   <li>Reconcile the TRL's declared record count against the loaded row count
 *       (mirrors {@code ReconciliationEngine.reconcile_with_bigquery}).</li>
 *   <li>Create/update the job-control record throughout (mirrors
 *       {@code JobControlRepository.create_job/update_status/mark_failed}).</li>
 * </ol>
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

        // 5. Stage valid rows to NDJSON and bulk-load into BigQuery.
        long loadedCount = 0L;
        if (!validRows.isEmpty()) {
            String stagingUri = stagingPathPrefix + "/" + entity + "/" + runId + ".ndjson";
            blobStore.put(stagingUri, toNdjson(validRows));
            loadedCount = warehouse.loadFromUri(stagingUri, request.targetTable(), schema);
        }

        // 6. Quarantine invalid rows (schema violations + CSV parse errors).
        List<FailedRowRecord> quarantineRecords = new ArrayList<>(
                InvalidRowAdapter.adaptAll(invalidRows, Function.identity()));
        quarantineRecords.addAll(parseErrorsToFailedRowRecords(parseErrors));

        if (!quarantineRecords.isEmpty()) {
            QuarantineHandler quarantineHandler =
                    new QuarantineHandler(blobStore, jobControlRepository, errorPathPrefix);
            quarantineHandler.writeFailures(runId, quarantineRecords);
        }

        // 7. Reconcile declared vs. loaded counts.
        ReconciliationResult reconciliation =
                new ReconciliationResult(envelope.trailer().recordCount(), loadedCount);
        if (!reconciliation.isReconciled()) {
            jobControlRepository.markFailed(runId, "RECONCILIATION_MISMATCH",
                    "Expected " + reconciliation.expectedCount() + " rows, loaded "
                            + reconciliation.actualCount(),
                    FailureStage.RECONCILIATION, Optional.empty());
        }

        return new IngestionResult(
                runId, entity, candidateRows.size(), validRows.size(),
                invalidRows.size() + parseErrors.size(), loadedCount, reconciliation);
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
