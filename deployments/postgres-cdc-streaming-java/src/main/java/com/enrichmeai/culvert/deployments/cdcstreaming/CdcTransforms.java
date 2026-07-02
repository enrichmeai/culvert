package com.enrichmeai.culvert.deployments.cdcstreaming;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Pure record-shaping functions mirroring
 * {@code streaming_pipeline.pipeline.transforms} (gcp-pipeline-reference
 * deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/transforms.py).
 *
 * <p>Kept as plain static methods (not Beam {@code DoFn}s) so they are
 * trivially unit-testable and reusable from either a {@link CdcParseStage}
 * (single-shot execute, current Culvert Dataflow adapter) or a future
 * element-level Beam translation. See README.md for why this deployment
 * does not yet wire true per-element Beam windowing.
 */
public final class CdcTransforms {

    private CdcTransforms() {
    }

    /**
     * ODP (Operational Data Platform) shaping: mirrors
     * {@code TransformToODPDoFn.process} (transforms.py:35-44) — strips
     * {@code null}-valued keys so BigQuery NULLABLE columns simply omit the
     * key rather than carry an explicit null that could conflict with a
     * REQUIRED constraint.
     *
     * @param element A parsed CDC record (see {@link CdcEventParser}), with
     *                CDC metadata keys already merged in by the caller.
     * @return A new map with all {@code null}-valued entries removed.
     */
    public static Map<String, Object> toOdp(Map<String, Object> element) {
        Objects.requireNonNull(element, "element must not be null");
        Map<String, Object> record = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : element.entrySet()) {
            if (entry.getValue() != null) {
                record.put(entry.getKey(), entry.getValue());
            }
        }
        return record;
    }

    /**
     * Inject audit columns, mirroring {@code AddStreamingAuditDoFn.process}
     * (transforms.py:116-132): adds {@code _run_id} and {@code _processed_at}
     * (ISO-8601 UTC "now").
     *
     * @param element The ODP-shaped record.
     * @param runId   The pipeline run identifier
     *                ({@link com.enrichmeai.culvert.contracts.RuntimeContext#runId()}).
     * @return A new map with the two audit columns appended.
     */
    public static Map<String, Object> addStreamingAudit(Map<String, Object> element, String runId) {
        Objects.requireNonNull(element, "element must not be null");
        Objects.requireNonNull(runId, "runId must not be null");
        Map<String, Object> record = new LinkedHashMap<>(element);
        record.put("_run_id", runId);
        record.put("_processed_at", Instant.now().toString());
        return record;
    }

    /**
     * FDP (Feature Data Platform) shaping: mirrors
     * {@code TransformToFDPDoFn.process} (transforms.py:65-113) —
     * derives {@code full_name}, extracts/masks {@code email_domain},
     * masks {@code ssn} into {@code ssn_masked}, and stamps window
     * boundaries.
     *
     * <p>The Python version reads {@code window.start}/{@code window.end}
     * from Beam's {@code WindowParam} (transforms.py:94-102, falling back to
     * "now" for the {@code GlobalWindow}/non-windowed case). This port takes
     * the window boundaries as explicit parameters so callers control
     * windowing directly — see README.md "Streaming semantics caveats" for
     * why this deployment does not (yet) drive them from a live Beam
     * {@code WindowFn}.
     *
     * @param element       The parsed CDC record (pre-ODP-shaping is fine;
     *                      this method reads {@code customer_id},
     *                      {@code first_name}/{@code last_name}/{@code name},
     *                      {@code email}, {@code status}, {@code ssn}, and
     *                      the {@code _cdc_operation}/{@code _cdc_event_time}
     *                      metadata keys).
     * @param maskPii       When true (production default, matches
     *                      {@code mask_pii=True} in runner.py:302), mask SSN
     *                      and email-domain fields.
     * @param windowStartIso ISO-8601 UTC window start boundary.
     * @param windowEndIso   ISO-8601 UTC window end boundary.
     * @return The FDP-shaped record.
     */
    public static Map<String, Object> toFdp(Map<String, Object> element,
                                             boolean maskPii,
                                             String windowStartIso,
                                             String windowEndIso) {
        Objects.requireNonNull(element, "element must not be null");
        Objects.requireNonNull(windowStartIso, "windowStartIso must not be null");
        Objects.requireNonNull(windowEndIso, "windowEndIso must not be null");

        Map<String, Object> record = new LinkedHashMap<>();

        record.put("customer_id", element.get("customer_id"));

        String first = stringOrEmpty(element.get("first_name"));
        String last = stringOrEmpty(element.get("last_name"));
        String name = stringOrEmpty(element.get("name"));
        String fullName = (!first.isEmpty() || !last.isEmpty())
                ? (first + " " + last).strip()
                : name;
        record.put("full_name", fullName);

        String email = stringOrEmpty(element.get("email"));
        if (!email.isEmpty() && email.contains("@")) {
            record.put("email_domain", maskPii ? "****" : email.substring(email.indexOf('@') + 1));
        } else {
            record.put("email_domain", null);
        }

        record.put("status", element.get("status"));

        Object ssnValue = element.get("ssn");
        String ssn = ssnValue == null ? "" : String.valueOf(ssnValue);
        if (maskPii && !ssn.isEmpty()) {
            record.put("ssn_masked", ssn.length() >= 4
                    ? "XXX-XX-" + ssn.substring(ssn.length() - 4)
                    : "XXX-XX-****");
        } else {
            record.put("ssn_masked", ssn.isEmpty() ? null : ssn);
        }

        record.put("window_start", windowStartIso);
        record.put("window_end", windowEndIso);

        record.put("cdc_operation", element.get(CdcEventParser.FIELD_CDC_OPERATION));
        record.put("cdc_event_time", element.get(CdcEventParser.FIELD_CDC_EVENT_TIME));

        return record;
    }

    private static String stringOrEmpty(Object value) {
        return value == null ? "" : String.valueOf(value);
    }
}
