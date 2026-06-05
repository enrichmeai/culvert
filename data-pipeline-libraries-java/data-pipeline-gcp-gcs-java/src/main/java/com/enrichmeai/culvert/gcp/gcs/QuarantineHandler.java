package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Dead-letter / quarantine handler for failed pipeline rows.
 *
 * <p>Serialises rows that failed data-quality validation to a
 * newline-delimited JSON file in the configured {@link BlobStore} error
 * path, then calls
 * {@link JobControlRepository#markFailed(String, String, String, FailureStage, Optional)}
 * with the URI of the written file so the job-control table records
 * exactly where the bad rows went.
 *
 * <h2>Quarantine path convention</h2>
 * <pre>
 * &lt;errorPathPrefix&gt;/quarantine/&lt;runId&gt;/&lt;timestamp&gt;.jsonl
 * </pre>
 * {@code timestamp} is an ISO-8601 basic compact instant
 * ({@code yyyyMMdd'T'HHmmssSSS'Z'}) — no colons, safe as a GCS object-name
 * component. The timestamp is derived from the injected {@link Clock}
 * (default: {@link Clock#systemUTC()}) so tests can fix it and assert
 * the exact URI.
 *
 * <h2>Error-code / stage defaults</h2>
 * <ul>
 *   <li>{@code errorCode} — {@code "DQ_VALIDATION_FAILURE"}
 *   <li>{@code failureStage} — {@link FailureStage#VALIDATION} (per the
 *       enum's own javadoc: validation failures route to dead-letter/quarantine)
 *   <li>{@code errorMessage} — {@code "N row(s) failed data-quality validation;
 *       quarantined to <uri>"}
 * </ul>
 *
 * <h2>Empty-list behaviour</h2>
 * If {@code failures} is empty, {@code writeFailures} is a no-op: neither
 * {@link BlobStore#put} nor {@link JobControlRepository#markFailed} is
 * called.
 *
 * <h2>InvalidRow / T14.5 seam</h2>
 * The handler accepts {@link FailedRowRecord} rather than T14.1's concrete
 * {@code InvalidRow} (which does not exist on this branch). T14.5 wires the
 * two by having {@code InvalidRow} implement {@code FailedRowRecord}, or by
 * providing a one-line adapter record. No core edits are required.
 *
 * <p>Sprint-14 / issue #74 (T14.2).
 */
public final class QuarantineHandler {

    private static final Logger LOG = LoggerFactory.getLogger(QuarantineHandler.class);

    /** Fixed error-code recorded in the job-control table. */
    public static final String ERROR_CODE = "DQ_VALIDATION_FAILURE";

    /**
     * Timestamp formatter: ISO-8601 basic compact, UTC, no colons.
     * Example: {@code 20250604T143022123Z}.
     */
    private static final DateTimeFormatter TIMESTAMP_FMT =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmssSSS'Z'")
                    .withZone(java.time.ZoneOffset.UTC);

    private static final Gson GSON = new GsonBuilder().serializeNulls().create();

    private final BlobStore blobStore;
    private final JobControlRepository jobControlRepository;
    private final String errorPathPrefix;
    private final Clock clock;

    /**
     * Production constructor — uses the system UTC clock.
     *
     * @param blobStore            BlobStore to write quarantine files to.
     * @param jobControlRepository Repository to call {@code markFailed} on.
     * @param errorPathPrefix      Prefix URI without a trailing slash, e.g.
     *                             {@code gs://my-bucket/errors}. The handler
     *                             appends {@code /quarantine/<runId>/<ts>.jsonl}.
     */
    public QuarantineHandler(BlobStore blobStore,
                             JobControlRepository jobControlRepository,
                             String errorPathPrefix) {
        this(blobStore, jobControlRepository, errorPathPrefix, Clock.systemUTC());
    }

    /**
     * Test-friendly constructor — inject a fixed {@link Clock} to get a
     * deterministic timestamp in the written URI.
     *
     * @param blobStore            BlobStore implementation (may be a stub).
     * @param jobControlRepository JobControlRepository implementation (may be a stub).
     * @param errorPathPrefix      Prefix URI without trailing slash.
     * @param clock                Clock used to derive the file timestamp.
     */
    public QuarantineHandler(BlobStore blobStore,
                             JobControlRepository jobControlRepository,
                             String errorPathPrefix,
                             Clock clock) {
        this.blobStore = Objects.requireNonNull(blobStore, "blobStore must not be null");
        this.jobControlRepository = Objects.requireNonNull(
                jobControlRepository, "jobControlRepository must not be null");
        this.errorPathPrefix = normalisePrefix(
                Objects.requireNonNull(errorPathPrefix, "errorPathPrefix must not be null"));
        this.clock = Objects.requireNonNull(clock, "clock must not be null");
    }

    /**
     * Write failed rows to the quarantine path and call
     * {@link JobControlRepository#markFailed}.
     *
     * <p>If {@code failures} is empty this method returns immediately
     * without touching either the {@link BlobStore} or the
     * {@link JobControlRepository}.
     *
     * @param runId    Pipeline run identifier (used in the path and in
     *                 {@code markFailed}).
     * @param failures Rows that failed validation. Must not be null; may be
     *                 empty (no-op).
     */
    public void writeFailures(String runId, List<? extends FailedRowRecord> failures) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(failures, "failures must not be null");

        if (failures.isEmpty()) {
            LOG.debug("writeFailures: no failures for runId={} — skipping", runId);
            return;
        }

        Instant now = Instant.now(clock);
        String timestamp = TIMESTAMP_FMT.format(now);
        String quarantineUri = errorPathPrefix + "/quarantine/" + runId + "/" + timestamp + ".jsonl";

        byte[] ndjson = serialise(failures);
        blobStore.put(quarantineUri, ndjson);
        LOG.info("Quarantined {} row(s) for runId={} to {}", failures.size(), runId, quarantineUri);

        String errorMessage = failures.size() + " row(s) failed data-quality validation; quarantined to "
                + quarantineUri;
        jobControlRepository.markFailed(
                runId,
                ERROR_CODE,
                errorMessage,
                FailureStage.VALIDATION,
                Optional.of(quarantineUri));
    }

    // ---- Serialisation ----

    /**
     * Serialise the failure list as newline-delimited JSON (NDJSON / JSON-L).
     *
     * <p>Each line is a self-describing JSON object with two top-level keys:
     * <ul>
     *   <li>{@code "row"} — the field values from {@link FailedRowRecord#rowContent()}.
     *   <li>{@code "violations"} — list of {@code {"field": "...", "rule": "..."}} objects.
     * </ul>
     * The final byte sequence ends with a newline ({@code \n}) after the last
     * record, consistent with NDJSON convention.
     */
    static byte[] serialise(List<? extends FailedRowRecord> failures) {
        StringBuilder sb = new StringBuilder();
        for (FailedRowRecord record : failures) {
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("row", record.rowContent());

            List<Map<String, String>> violationList = record.violations().stream()
                    .map(v -> {
                        Map<String, String> m = new LinkedHashMap<>();
                        m.put("field", v.field());
                        m.put("rule", v.rule());
                        return m;
                    })
                    .collect(Collectors.toList());
            envelope.put("violations", violationList);

            sb.append(GSON.toJson(envelope)).append('\n');
        }
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    // ---- Helpers ----

    /**
     * Strip trailing slash from the prefix so we always join with exactly
     * one slash regardless of whether the caller included a trailing slash.
     */
    private static String normalisePrefix(String prefix) {
        return prefix.endsWith("/") ? prefix.substring(0, prefix.length() - 1) : prefix;
    }
}
