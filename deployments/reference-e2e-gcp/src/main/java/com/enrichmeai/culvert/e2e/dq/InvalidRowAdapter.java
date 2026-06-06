package com.enrichmeai.culvert.e2e.dq;

import com.enrichmeai.culvert.dataquality.FieldViolation;
import com.enrichmeai.culvert.dataquality.ValidationResult;
import com.enrichmeai.culvert.gcp.gcs.FailedRowRecord;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Seam adapter: bridges T14.1's {@link ValidationResult.InvalidRow} (core) to
 * T14.2's {@link FailedRowRecord} (gcs).
 *
 * <h2>R-vs-Map reconciliation</h2>
 * <p>{@code InvalidRow<R>} stores the original row as a generic {@code R} — it
 * does not itself hold a {@code Map<String,Object>}.  {@code FailedRowRecord}
 * requires {@link FailedRowRecord#rowContent()} to return
 * {@code Map<String,Object>}.  The bridge is the <em>same
 * {@code Function<R, Map<String,Object>>} accessor</em> that
 * {@link com.enrichmeai.culvert.dataquality.DataQualityTransform} was constructed
 * with — we re-apply it to {@code invalidRow.row()} to project the row into its
 * field map.
 *
 * <p>When {@code R} is already {@code Map<String,Object>} (as in the reference
 * pipeline) the accessor is {@code Function.identity()} and the round-trip is
 * exact: the same map object flows through unchanged.
 *
 * <h2>Violation mapping</h2>
 * <p>{@link FieldViolation} carries three fields:
 * <ul>
 *   <li>{@code fieldName()} — maps to {@link FailedRowRecord.ViolationDescriptor#field()}</li>
 *   <li>{@code detail()} — maps to {@link FailedRowRecord.ViolationDescriptor#rule()}
 *       (detail is the human-readable rule message; {@code violationKind} is the
 *       structural category and is not surfaced by the seam interface)</li>
 * </ul>
 *
 * <h2>Live GCS URI pattern (for reference)</h2>
 * <p>When wiring to a real {@link com.enrichmeai.culvert.gcp.gcs.QuarantineHandler}
 * in production, the {@code errorPathPrefix} follows this convention:
 * <pre>
 *   gs://&lt;bucket&gt;/errors/&lt;pipeline-id&gt;
 * </pre>
 * The handler appends {@code /quarantine/&lt;runId&gt;/&lt;timestamp&gt;.jsonl}.
 * Example: {@code gs://culvert-errors-prod/errors/reference-e2e-gcp/quarantine/run-abc/20260601T120000000Z.jsonl}
 *
 * <p>Sprint-14 / issue #82 (T14.5) — the E2E seam proof.
 */
public final class InvalidRowAdapter {

    private InvalidRowAdapter() {
        // utility class
    }

    /**
     * Adapt a single {@link ValidationResult.InvalidRow} to a {@link FailedRowRecord}.
     *
     * @param <R>       The row type used by the pipeline.
     * @param invalidRow The invalid row to adapt. Must not be null.
     * @param rowToMap   Accessor that projects {@code R} into its field map.
     *                   When {@code R = Map<String,Object>} use {@code Function.identity()}.
     *                   The returned map must not be null.
     * @return A {@link FailedRowRecord} whose {@code rowContent()} is the projected
     *         map and whose {@code violations()} carry the field+rule pairs.
     */
    public static <R> FailedRowRecord adapt(
            ValidationResult.InvalidRow<R> invalidRow,
            Function<R, Map<String, Object>> rowToMap) {

        Objects.requireNonNull(invalidRow, "invalidRow must not be null");
        Objects.requireNonNull(rowToMap,   "rowToMap must not be null");

        Map<String, Object> content = rowToMap.apply(invalidRow.row());
        List<ViolationDescriptorImpl> vds = invalidRow.violations().stream()
                .map(fv -> new ViolationDescriptorImpl(fv.fieldName(), fv.detail()))
                .collect(Collectors.toUnmodifiableList());

        return new AdaptedFailedRowRecord(content, vds);
    }

    /**
     * Convenience overload: adapt a list of invalid rows all at once.
     *
     * @param <R>         The row type.
     * @param invalidRows Invalid rows to adapt. Must not be null; may be empty.
     * @param rowToMap    Accessor projecting {@code R} to its field map.
     * @return An unmodifiable list of adapted {@link FailedRowRecord} instances.
     */
    public static <R> List<FailedRowRecord> adaptAll(
            List<ValidationResult.InvalidRow<R>> invalidRows,
            Function<R, Map<String, Object>> rowToMap) {

        Objects.requireNonNull(invalidRows, "invalidRows must not be null");
        Objects.requireNonNull(rowToMap,    "rowToMap must not be null");

        return invalidRows.stream()
                .map(inv -> adapt(inv, rowToMap))
                .collect(Collectors.toUnmodifiableList());
    }

    // -----------------------------------------------------------------------
    // Internal record implementations
    // -----------------------------------------------------------------------

    /**
     * {@link FailedRowRecord} implementation backed by the adapter's projected map
     * and translated violation list.
     *
     * <p>Implemented as a class (not a record) so that the {@link #violations()}
     * accessor can return the covariant type
     * {@code List<? extends FailedRowRecord.ViolationDescriptor>} required by the
     * interface. Java records enforce that the accessor return type exactly matches
     * the component type, which would conflict with the wildcard in the interface.
     */
    private static final class AdaptedFailedRowRecord implements FailedRowRecord {

        private final Map<String, Object> content;
        private final List<ViolationDescriptorImpl> vds;

        AdaptedFailedRowRecord(Map<String, Object> content, List<ViolationDescriptorImpl> vds) {
            this.content = content;
            this.vds     = vds;
        }

        @Override
        public Map<String, Object> rowContent() {
            return content;
        }

        @Override
        public List<? extends FailedRowRecord.ViolationDescriptor> violations() {
            return vds;
        }
    }

    /**
     * {@link FailedRowRecord.ViolationDescriptor} record that holds the field name and
     * rule (mapped from {@link FieldViolation#fieldName()} and
     * {@link FieldViolation#detail()}).
     */
    private record ViolationDescriptorImpl(String field, String rule)
            implements FailedRowRecord.ViolationDescriptor {
    }
}
