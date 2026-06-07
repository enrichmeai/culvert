package com.enrichmeai.culvert.dataquality;

import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.Transform;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.Masker;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * A cloud-neutral {@link Transform} that validates each row against an
 * {@link EntitySchema} and classifies it as either a {@link ValidationResult.ValidRow}
 * or an {@link ValidationResult.InvalidRow} (with a full list of
 * {@link FieldViolation} instances — one per failing field).
 *
 * <h2>Validation rules (applied in order per field)</h2>
 * <ol>
 *   <li><strong>MISSING_REQUIRED</strong> — a field whose {@code mode} is
 *       {@code "REQUIRED"} has a {@code null} or absent value in the row map.</li>
 *   <li><strong>TYPE_MISMATCH</strong> — the field value is non-null but its
 *       runtime class is not assignable from the expected Java type for the wire
 *       type declared in the schema:
 *       <pre>
 *         STRING  → String
 *         INT64   → Long (or Integer, widened)
 *         FLOAT64 → Double (or Float, widened)
 *         BOOL    → Boolean
 *       </pre>
 *       Other wire types pass the type check (no known mapping).</li>
 *   <li><strong>OUT_OF_RANGE</strong> — the {@link SchemaField} carries a
 *       {@link NumericRange} (via {@link SchemaField#range()}) and the value,
 *       after conversion to {@code double}, falls outside {@code [min, max]}.
 *       This check is skipped if the value is null or already flagged with a
 *       type mismatch. No separate side-map is required — bounds live in the
 *       schema definition.</li>
 * </ol>
 *
 * <h2>All violations are accumulated</h2>
 * <p>A row with N failing fields produces an {@link ValidationResult.InvalidRow}
 * with N {@link FieldViolation} entries. Validation does not short-circuit on the
 * first failure.
 *
 * <h2>Usage — direct row validation</h2>
 * <pre>{@code
 * EntitySchema schema = EntitySchema.of("order", List.of(
 *         SchemaField.required("id",    "STRING"),
 *         SchemaField.required("amount","FLOAT64").withRange(NumericRange.of(0.0, 1_000_000.0)),
 *         SchemaField.nullable("note",  "STRING")));
 *
 * DataQualityTransform<Map<String,Object>> dq =
 *         new DataQualityTransform<>(schema, Function.identity());
 *
 * ValidationResult<Map<String,Object>> result = dq.validate(row);
 * if (result instanceof ValidationResult.ValidRow<Map<String,Object>> v) {
 *     downstreamSink.write(v.row());
 * } else if (result instanceof ValidationResult.InvalidRow<Map<String,Object>> inv) {
 *     deadLetterSink.write(inv);  // T14.2
 * }
 * }</pre>
 *
 * <h2>Usage — as a {@link Transform} in a pipeline stage</h2>
 * <pre>{@code
 * Transform<Map<String,Object>, ValidationResult<Map<String,Object>>> transform = dq;
 * Iterator<ValidationResult<Map<String,Object>>> results =
 *         transform.apply(inputIterator, runtimeContext);
 * }</pre>
 *
 * <p>The {@link #apply(Iterator, RuntimeContext)} implementation is lazy — it
 * wraps the input iterator with a mapping iterator and does not materialise the
 * full input. After the iterator is exhausted, one {@link StageMetrics} snapshot
 * is emitted via {@code context.stageMetrics()} with the total rows processed
 * and the count of invalid rows as errors.
 *
 * <h2>Zero cloud/Beam dependencies</h2>
 * <p>No {@code org.apache.beam.*} or {@code com.enrichmeai.culvert.gcp.*} imports.
 *
 * <h2>PII masking (opt-in, T14.4)</h2>
 * <p>An optional {@link GovernancePolicy} may be supplied at construction time.
 * When present, after a row passes all validation checks the transform iterates
 * the row's field map and applies masking to any field for which
 * {@link GovernancePolicy#maskingFor(String, String)} returns a non-empty policy.
 * The table name passed to {@code maskingFor} is {@code schema.name()}.
 * <p>Masking is a <em>post-validation</em> step: it runs only on
 * {@link ValidationResult.ValidRow} results, after all violation checks are
 * complete. Invalid rows are never masked.
 * <p>Backward-compat: when no policy is supplied (the original no-policy constructor),
 * masking is fully skipped — all existing tests are unaffected.
 * <p><strong>Mutable-map requirement:</strong> masking mutates the map returned
 * by the row accessor in place. Accessor implementations that return immutable
 * maps (e.g. {@code Map.of(...)}) will throw on {@code put}. Use a mutable
 * {@code HashMap} when masking is enabled.
 *
 * @param <R> The row type. The row-to-field-map accessor is supplied at
 *            construction time via a {@code Function<R, Map<String,Object>>}.
 *
 * @since Sprint 14 / issue #73 (T14.1); masking added T14.4 / issue #76;
 *        schema-grounded range validation T14.7 / issue #100
 */
public final class DataQualityTransform<R>
        implements Transform<R, ValidationResult<R>> {

    /** Maps schema wire types to expected Java types. */
    private static final Map<String, Class<?>> WIRE_TYPE_MAP = Map.of(
            "STRING",  String.class,
            "INT64",   Number.class,   // Long is Number; accept Integer widened too
            "FLOAT64", Number.class,   // Double and Float are both Number
            "BOOL",    Boolean.class
    );

    private final EntitySchema schema;
    private final java.util.function.Function<R, Map<String, Object>> rowAccessor;

    /**
     * Optional governance policy for PII masking. Null means masking is disabled
     * (backward-compatible default — the no-policy constructor leaves this null).
     */
    private final GovernancePolicy governancePolicy;

    // ---------------------------------------------------------------
    // Constructors
    // ---------------------------------------------------------------

    /**
     * Schema-only convenience constructor (no masking policy).
     *
     * <p>Range validation is driven entirely by
     * {@link SchemaField#range()} — no side-map required.
     *
     * @param schema      The schema to validate each row against.
     * @param rowAccessor Extracts a {@code Map<fieldName, value>} from a row.
     */
    public DataQualityTransform(
            EntitySchema schema,
            java.util.function.Function<R, Map<String, Object>> rowAccessor) {
        this(schema, rowAccessor, null);
    }

    /**
     * Full constructor with an optional governance policy for PII masking.
     *
     * <p>Range validation is driven by {@link SchemaField#range()} — no side-map
     * is accepted or required.
     *
     * <p>When {@code policy} is non-null, matched fields in passing rows are
     * masked in place (see class javadoc for the mutable-map requirement).
     *
     * @param schema      The schema to validate each row against.
     * @param rowAccessor Extracts a {@code Map<fieldName, value>} from a row.
     * @param policy      Optional governance policy for PII masking.
     *                    Pass {@code null} to disable masking (default).
     */
    public DataQualityTransform(
            EntitySchema schema,
            java.util.function.Function<R, Map<String, Object>> rowAccessor,
            GovernancePolicy policy) {
        this.schema           = Objects.requireNonNull(schema,      "schema must not be null");
        this.rowAccessor      = Objects.requireNonNull(rowAccessor, "rowAccessor must not be null");
        this.governancePolicy = policy; // null ⇒ masking disabled
    }

    // ---------------------------------------------------------------
    // Public API: per-row validation
    // ---------------------------------------------------------------

    /**
     * Validates a single row against the {@link EntitySchema}.
     *
     * <p>All violations are accumulated before returning; validation does not
     * short-circuit on the first failure.
     *
     * @param row The row to validate. Must not be null.
     * @return {@link ValidationResult.ValidRow} if no violations were found;
     *         {@link ValidationResult.InvalidRow} with all violations otherwise.
     */
    public ValidationResult<R> validate(R row) {
        Objects.requireNonNull(row, "row must not be null");
        Map<String, Object> fields = rowAccessor.apply(row);

        List<FieldViolation> violations = new ArrayList<>();

        for (SchemaField field : schema.fields()) {
            Object value = (fields != null) ? fields.get(field.name()) : null;

            // 1 — MISSING_REQUIRED
            if ("REQUIRED".equals(field.mode()) && value == null) {
                violations.add(new FieldViolation(
                        field.name(),
                        ViolationKind.MISSING_REQUIRED,
                        "Field '" + field.name() + "' is REQUIRED but was null or absent"));
                continue; // no point type-checking a null
            }

            if (value == null) {
                // nullable/repeated field with null value — no further checks
                continue;
            }

            // 2 — TYPE_MISMATCH
            Class<?> expected = WIRE_TYPE_MAP.get(field.type());
            boolean typeMismatch = false;
            if (expected != null && !expected.isInstance(value)) {
                violations.add(new FieldViolation(
                        field.name(),
                        ViolationKind.TYPE_MISMATCH,
                        "Field '" + field.name() + "' expected type compatible with "
                                + field.type() + " (" + expected.getSimpleName()
                                + ") but got " + value.getClass().getSimpleName()
                                + " [value=" + value + "]"));
                typeMismatch = true;
            }

            // 3 — OUT_OF_RANGE (schema-grounded: bounds come from SchemaField.range())
            if (!typeMismatch) {
                Optional<NumericRange> rangeOpt = field.range();
                if (rangeOpt.isPresent() && value instanceof Number num) {
                    NumericRange range = rangeOpt.get();
                    double d = num.doubleValue();
                    if (!range.contains(d)) {
                        violations.add(new FieldViolation(
                                field.name(),
                                ViolationKind.OUT_OF_RANGE,
                                "Field '" + field.name() + "' value " + d
                                        + " is outside range [" + range.min()
                                        + ", " + range.max() + "]"));
                    }
                }
            }
        }

        if (!violations.isEmpty()) {
            return new ValidationResult.InvalidRow<>(row, violations);
        }

        // ---- Post-validation PII masking (opt-in, T14.4) -----
        // Apply masking only when a GovernancePolicy is configured.
        // Invalid rows are never masked — the dead-letter path receives the
        // original values so violations can be diagnosed.
        if (governancePolicy != null && fields != null) {
            String tableName = schema.name();
            for (Map.Entry<String, Object> entry : fields.entrySet()) {
                Optional<MaskingPolicy> mp =
                        governancePolicy.maskingFor(entry.getKey(), tableName);
                if (mp.isPresent()) {
                    entry.setValue(Masker.mask(entry.getValue(), mp.get()));
                }
            }
        }

        return new ValidationResult.ValidRow<>(row);
    }

    // ---------------------------------------------------------------
    // Transform<R, ValidationResult<R>> implementation
    // ---------------------------------------------------------------

    /**
     * Lazily maps {@link #validate(Object)} over the input iterator.
     *
     * <p>The returned iterator is a thin wrapper; rows are validated on demand
     * as the caller calls {@code next()}. The input is not materialised.
     *
     * <p>After the iterator is exhausted, one {@link StageMetrics} snapshot is
     * emitted via {@code context.stageMetrics()}: {@code rowsProcessed} = total
     * rows seen; {@code errorCount} = count of invalid rows;
     * {@code stageLatencyMs} = elapsed wall-clock time from the first call to
     * {@code next()} to iterator exhaustion.
     *
     * @param records The input rows.
     * @param context The runtime context (used for {@code stageMetrics()} emission).
     * @return A lazy iterator of {@link ValidationResult} instances.
     */
    @Override
    public Iterator<ValidationResult<R>> apply(
            Iterator<R> records, RuntimeContext context) {
        Objects.requireNonNull(records, "records must not be null");
        Objects.requireNonNull(context, "context must not be null");
        return new ValidatingIterator(records, context);
    }

    // ---------------------------------------------------------------
    // Inner iterator
    // ---------------------------------------------------------------

    private final class ValidatingIterator implements Iterator<ValidationResult<R>> {

        private final Iterator<R>    source;
        private final RuntimeContext context;

        private long rowsProcessed = 0L;
        private long errorCount    = 0L;
        private long startNanos    = -1L;

        ValidatingIterator(Iterator<R> source, RuntimeContext context) {
            this.source  = source;
            this.context = context;
        }

        @Override
        public boolean hasNext() {
            boolean more = source.hasNext();
            if (!more) {
                emitMetrics();
            }
            return more;
        }

        @Override
        public ValidationResult<R> next() {
            if (startNanos < 0) {
                startNanos = System.nanoTime();
            }
            ValidationResult<R> result = validate(source.next());
            rowsProcessed++;
            if (!result.isValid()) {
                errorCount++;
            }
            // Emit after last row (when iterator now empty)
            if (!source.hasNext()) {
                emitMetrics();
            }
            return result;
        }

        /**
         * Emits a single {@link StageMetrics} snapshot.
         * Guard ensures we emit exactly once even if hasNext() and next() both
         * detect exhaustion.
         */
        private boolean emitted = false;

        private void emitMetrics() {
            if (emitted) return;
            emitted = true;
            long elapsedNanos = (startNanos < 0) ? 0L : System.nanoTime() - startNanos;
            double latencyMs  = elapsedNanos / 1_000_000.0;
            try {
                context.stageMetrics().recordStageMetrics(new StageMetrics(
                        context.pipelineId(),
                        context.runId(),
                        "DataQualityTransform",
                        rowsProcessed,
                        latencyMs,
                        errorCount));
            } catch (Exception ex) {
                // Advisory — never let metrics emission break the pipeline.
                // (Same swallow-on-error contract as StageMetricsHook Javadoc)
            }
        }
    }
}
