package com.enrichmeai.culvert.dataquality;

import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.MaskingStrategy;
import com.enrichmeai.culvert.governance.PiiMaskingGovernancePolicy;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link DataQualityTransform}.
 *
 * <p>Covers the five DoD boxes from issue #73:
 * <ol>
 *   <li>Valid row passes through unchanged.</li>
 *   <li>Missing required field → {@code MISSING_REQUIRED} violation.</li>
 *   <li>Type mismatch → {@code TYPE_MISMATCH} violation.</li>
 *   <li>Out-of-range value → {@code OUT_OF_RANGE} violation.</li>
 *   <li>Multi-field row with mixed violations accumulates all entries.</li>
 * </ol>
 *
 * <p>Also covers:
 * <ul>
 *   <li>{@link DataQualityTransform#apply(Iterator, RuntimeContext)} emits
 *       {@link StageMetrics} via {@link StageMetricsHook} after iteration.</li>
 * </ul>
 *
 * @since Sprint 14 / issue #73
 */
class DataQualityTransformTest {

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /** Convenience schema for most tests. */
    private static EntitySchema schemaWith(SchemaField... fields) {
        return EntitySchema.of("test_entity", List.of(fields));
    }

    /** Simple row: a Map with the given key/value pairs. */
    @SafeVarargs
    private static Map<String, Object> row(Map.Entry<String, Object>... entries) {
        Map<String, Object> m = new HashMap<>();
        for (Map.Entry<String, Object> e : entries) {
            m.put(e.getKey(), e.getValue());
        }
        return m;
    }

    private static Map.Entry<String, Object> field(String key, Object value) {
        return Map.entry(key, value);
    }

    /**
     * Returns a {@link RuntimeContext} backed by the recording hook so we can
     * assert on emitted metrics.
     */
    private static TestSetup makeContext(CapturingMetricsHook hook) {
        DefaultRuntimeContext ctx = DefaultRuntimeContext.builder("run-test", "test").build();
        ctx.register(StageMetricsHook.class, hook);
        return new TestSetup(ctx, hook);
    }

    private record TestSetup(DefaultRuntimeContext ctx, CapturingMetricsHook hook) {}

    /** Minimal {@link StageMetricsHook} that captures all calls. */
    private static final class CapturingMetricsHook implements StageMetricsHook {
        final List<StageMetrics> captured = new ArrayList<>();

        @Override
        public void recordStageMetrics(StageMetrics metrics) {
            captured.add(metrics);
        }
    }

    /** Identity accessor for {@code Map<String,Object>} rows. */
    private static final Function<Map<String, Object>, Map<String, Object>> ID = Function.identity();

    // ------------------------------------------------------------------
    // DoD Box 1 — valid row passes through unchanged
    // ------------------------------------------------------------------

    @Test
    void valid_row_produces_valid_result() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",    "STRING"),
                SchemaField.required("score", "FLOAT64"),
                SchemaField.nullable("note",  "STRING"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        Map<String, Object> inputRow = row(
                field("id",    "abc"),
                field("score", 99.0),
                field("note",  "ok"));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.ValidRow.class);
        assertThat(result.isValid()).isTrue();
        assertThat(result.row()).isSameAs(inputRow);
    }

    @Test
    void nullable_field_with_null_value_is_valid() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",   "STRING"),
                SchemaField.nullable("note", "STRING"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        // "note" is nullable — null value is allowed
        Map<String, Object> inputRow = new HashMap<>();
        inputRow.put("id",   "x");
        inputRow.put("note", null);

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result.isValid()).isTrue();
    }

    // ------------------------------------------------------------------
    // DoD Box 2 — missing required field → MISSING_REQUIRED
    // ------------------------------------------------------------------

    @Test
    void missing_required_field_produces_missing_required_violation() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",   "STRING"),
                SchemaField.required("name", "STRING"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        // "name" is required but absent
        Map<String, Object> inputRow = row(field("id", "42"));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalid =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;

        assertThat(invalid.violations()).hasSize(1);
        FieldViolation v = invalid.violations().get(0);
        assertThat(v.fieldName()).isEqualTo("name");
        assertThat(v.violationKind()).isEqualTo(ViolationKind.MISSING_REQUIRED);
        assertThat(v.detail()).contains("name");
    }

    @Test
    void required_field_present_but_null_produces_missing_required_violation() {
        EntitySchema schema = schemaWith(SchemaField.required("id", "STRING"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        Map<String, Object> inputRow = new HashMap<>();
        inputRow.put("id", null);   // present key, null value

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalid =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;
        assertThat(invalid.violations().get(0).violationKind())
                .isEqualTo(ViolationKind.MISSING_REQUIRED);
    }

    // ------------------------------------------------------------------
    // DoD Box 3 — type mismatch → TYPE_MISMATCH
    // ------------------------------------------------------------------

    @Test
    void wrong_type_produces_type_mismatch_violation() {
        EntitySchema schema = schemaWith(SchemaField.required("count", "INT64"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        // count is INT64 but we pass a String
        Map<String, Object> inputRow = row(field("count", "not-a-number"));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalid =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;

        assertThat(invalid.violations()).hasSize(1);
        FieldViolation v = invalid.violations().get(0);
        assertThat(v.fieldName()).isEqualTo("count");
        assertThat(v.violationKind()).isEqualTo(ViolationKind.TYPE_MISMATCH);
        assertThat(v.detail()).contains("INT64");
    }

    @Test
    void bool_field_with_string_value_is_type_mismatch() {
        EntitySchema schema = schemaWith(SchemaField.required("active", "BOOL"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        Map<String, Object> inputRow = row(field("active", "yes")); // should be Boolean

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        assertThat(((ValidationResult.InvalidRow<Map<String, Object>>) result)
                .violations().get(0).violationKind())
                .isEqualTo(ViolationKind.TYPE_MISMATCH);
    }

    @Test
    void unknown_wire_type_does_not_produce_type_mismatch() {
        // Unknown types pass the type check — no mapping, no rule
        EntitySchema schema = schemaWith(SchemaField.required("blob", "BYTES"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        Map<String, Object> inputRow = row(field("blob", new byte[]{1, 2, 3}));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result.isValid()).isTrue();
    }

    // ------------------------------------------------------------------
    // DoD Box 4 — out-of-range → OUT_OF_RANGE
    // ------------------------------------------------------------------

    @Test
    void value_below_min_produces_out_of_range_violation() {
        EntitySchema schema = schemaWith(SchemaField.required("age", "INT64"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(
                        schema, ID,
                        Map.of("age", NumericRange.of(0, 150)));

        Map<String, Object> inputRow = row(field("age", -1L));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalid =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;

        assertThat(invalid.violations()).hasSize(1);
        FieldViolation v = invalid.violations().get(0);
        assertThat(v.fieldName()).isEqualTo("age");
        assertThat(v.violationKind()).isEqualTo(ViolationKind.OUT_OF_RANGE);
        assertThat(v.detail()).contains("-1");
    }

    @Test
    void value_above_max_produces_out_of_range_violation() {
        EntitySchema schema = schemaWith(SchemaField.required("score", "FLOAT64"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(
                        schema, ID,
                        Map.of("score", NumericRange.of(0.0, 100.0)));

        Map<String, Object> inputRow = row(field("score", 101.5));

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        FieldViolation v = ((ValidationResult.InvalidRow<Map<String, Object>>) result)
                .violations().get(0);
        assertThat(v.violationKind()).isEqualTo(ViolationKind.OUT_OF_RANGE);
    }

    @Test
    void value_at_boundary_is_valid() {
        EntitySchema schema = schemaWith(SchemaField.required("score", "FLOAT64"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(
                        schema, ID,
                        Map.of("score", NumericRange.of(0.0, 100.0)));

        assertThat(dq.validate(row(field("score", 0.0))).isValid()).isTrue();
        assertThat(dq.validate(row(field("score", 100.0))).isValid()).isTrue();
    }

    // ------------------------------------------------------------------
    // DoD Box 5 — multi-field mixed violations are accumulated
    // ------------------------------------------------------------------

    @Test
    void multi_field_row_accumulates_all_violations() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",     "STRING"),   // → MISSING_REQUIRED
                SchemaField.required("count",  "INT64"),    // → TYPE_MISMATCH (String)
                SchemaField.required("score",  "FLOAT64"),  // → OUT_OF_RANGE
                SchemaField.nullable("note",   "STRING"));  // → valid (nullable, null ok)

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(
                        schema, ID,
                        Map.of("score", NumericRange.of(0.0, 10.0)));

        Map<String, Object> inputRow = new HashMap<>();
        // "id" absent (MISSING_REQUIRED)
        inputRow.put("count", "bad-type");    // TYPE_MISMATCH
        inputRow.put("score", 999.9);         // OUT_OF_RANGE
        inputRow.put("note",  null);          // nullable null — OK

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        ValidationResult.InvalidRow<Map<String, Object>> invalid =
                (ValidationResult.InvalidRow<Map<String, Object>>) result;

        assertThat(invalid.violations()).hasSize(3);

        List<ViolationKind> kinds = invalid.violations().stream()
                .map(FieldViolation::violationKind)
                .toList();
        assertThat(kinds).containsExactlyInAnyOrder(
                ViolationKind.MISSING_REQUIRED,
                ViolationKind.TYPE_MISMATCH,
                ViolationKind.OUT_OF_RANGE);
    }

    // ------------------------------------------------------------------
    // apply() — Transform contract + StageMetrics emission
    // ------------------------------------------------------------------

    @Test
    void apply_returns_lazy_iterator_over_all_rows() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id", "STRING"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        List<Map<String, Object>> rows = List.of(
                row(field("id", "a")),
                row(field("id", "b")),
                row(field("id", "c")));

        CapturingMetricsHook hook = new CapturingMetricsHook();
        TestSetup setup = makeContext(hook);

        Iterator<ValidationResult<Map<String, Object>>> it =
                dq.apply(rows.iterator(), setup.ctx());

        List<ValidationResult<Map<String, Object>>> results = new ArrayList<>();
        it.forEachRemaining(results::add);

        assertThat(results).hasSize(3);
        assertThat(results).allMatch(ValidationResult::isValid);
    }

    @Test
    void apply_emits_stage_metrics_after_exhaustion() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",    "STRING"),
                SchemaField.required("value", "INT64"));

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        // 2 valid + 1 invalid (missing "value")
        Map<String, Object> validRow1 = row(field("id", "a"), field("value", 1L));
        Map<String, Object> validRow2 = row(field("id", "b"), field("value", 2L));
        Map<String, Object> badRow    = row(field("id", "c")); // missing "value"

        CapturingMetricsHook hook = new CapturingMetricsHook();
        TestSetup setup = makeContext(hook);

        Iterator<ValidationResult<Map<String, Object>>> it =
                dq.apply(List.of(validRow1, validRow2, badRow).iterator(), setup.ctx());
        it.forEachRemaining(r -> { /* drain */ });

        assertThat(hook.captured).hasSize(1);
        StageMetrics m = hook.captured.get(0);
        assertThat(m.stageName()).isEqualTo("DataQualityTransform");
        assertThat(m.rowsProcessed()).isEqualTo(3L);
        assertThat(m.errorCount()).isEqualTo(1L);
        assertThat(m.runId()).isEqualTo("run-test");
    }

    @Test
    void apply_emits_metrics_even_on_empty_iterator() {
        EntitySchema schema = schemaWith(SchemaField.required("id", "STRING"));
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID);

        CapturingMetricsHook hook = new CapturingMetricsHook();
        TestSetup setup = makeContext(hook);

        Iterator<ValidationResult<Map<String, Object>>> it =
                dq.apply(List.<Map<String, Object>>of().iterator(), setup.ctx());

        // hasNext() on empty iterator triggers the metric guard
        assertThat(it.hasNext()).isFalse();
        assertThat(hook.captured).hasSize(1);
        StageMetrics m = hook.captured.get(0);
        assertThat(m.rowsProcessed()).isEqualTo(0L);
        assertThat(m.errorCount()).isEqualTo(0L);
    }

    // ------------------------------------------------------------------
    // T14.4 — PII masking wired into DataQualityTransform (DoD Box 5)
    // ------------------------------------------------------------------

    /**
     * A passing row that contains a PII column ("email") should have that
     * field masked in the ValidRow result when a PiiMaskingGovernancePolicy
     * is wired in.  Non-PII fields must pass through unchanged.
     */
    @Test
    void dq_with_governance_policy_masks_pii_fields_in_valid_row() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",    "STRING"),
                SchemaField.required("email", "STRING"),
                SchemaField.required("score", "FLOAT64"));

        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .piiColumns(Set.of("email"))
                .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
                .build();

        // Must use a mutable HashMap — masking writes back via put().
        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID, policy);

        Map<String, Object> inputRow = new HashMap<>();
        inputRow.put("id",    "user-1");
        inputRow.put("email", "alice@example.com");
        inputRow.put("score", 88.0);

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.ValidRow.class);
        Map<String, Object> maskedRow = result.row();

        // PII field must be masked
        assertThat(maskedRow.get("email")).isEqualTo("***");
        // Non-PII fields must be unchanged
        assertThat(maskedRow.get("id")).isEqualTo("user-1");
        assertThat(maskedRow.get("score")).isEqualTo(88.0);
    }

    /**
     * A field matched by a regex pattern (not an explicit column-name entry)
     * must also be masked when a policy is wired in.
     */
    @Test
    void dq_with_governance_policy_masks_regex_matched_field() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",          "STRING"),
                SchemaField.required("card_pii",    "STRING"));

        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .piiPatterns(List.of(".*_pii$"))
                .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "REDACTED", ""))
                .build();

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID, policy);

        Map<String, Object> inputRow = new HashMap<>();
        inputRow.put("id",       "order-42");
        inputRow.put("card_pii", "4111-1111-1111-1111");

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result.isValid()).isTrue();
        assertThat(result.row().get("card_pii")).isEqualTo("REDACTED");
        assertThat(result.row().get("id")).isEqualTo("order-42");
    }

    /**
     * An invalid row (with a violation) must NOT be masked — it is returned
     * as-is so the dead-letter handler can inspect original values.
     */
    @Test
    void dq_with_governance_policy_does_not_mask_invalid_rows() {
        EntitySchema schema = schemaWith(
                SchemaField.required("id",    "STRING"),
                SchemaField.required("email", "STRING"));

        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .piiColumns(Set.of("email"))
                .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
                .build();

        DataQualityTransform<Map<String, Object>> dq =
                new DataQualityTransform<>(schema, ID, policy);

        // "id" is REQUIRED but absent → InvalidRow
        Map<String, Object> inputRow = new HashMap<>();
        inputRow.put("email", "bob@example.com");

        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        // Email must NOT be masked on the dead-letter path
        assertThat(result.row().get("email")).isEqualTo("bob@example.com");
    }

    /**
     * No-policy constructor path must be unaffected — backward compatibility.
     * The existing {@code valid_row_produces_valid_result} test already covers
     * this, but we add an explicit assertion that {@code row()} is the
     * identical reference (not a copy) even in the zero-policy path.
     */
    @Test
    void no_policy_path_returns_same_row_reference() {
        EntitySchema schema = schemaWith(SchemaField.required("id", "STRING"));
        DataQualityTransform<Map<String, Object>> dq = new DataQualityTransform<>(schema, ID);

        Map<String, Object> inputRow = row(field("id", "abc"));
        ValidationResult<Map<String, Object>> result = dq.validate(inputRow);

        assertThat(result.isValid()).isTrue();
        assertThat(result.row()).isSameAs(inputRow);
    }
}
