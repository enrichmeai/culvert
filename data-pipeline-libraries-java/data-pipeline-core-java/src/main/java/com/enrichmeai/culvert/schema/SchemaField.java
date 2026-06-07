package com.enrichmeai.culvert.schema;

import com.enrichmeai.culvert.dataquality.NumericRange;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;

import java.util.Optional;

/**
 * A single field in an {@link EntitySchema}.
 *
 * <p>{@code mode} is one of {@code REQUIRED}, {@code NULLABLE}, {@code REPEATED}
 * — the vocabulary matches BigQuery's (the framework's first reference
 * warehouse), but the values themselves are warehouse-neutral.
 *
 * <p>{@code classification} and {@code masking} are optional metadata used
 * by Stage 3's {@code @governed} and {@code @masked} decorators (Python) /
 * annotations (future Java) to apply field-level policy without requiring
 * an explicit decorator/annotation call.
 *
 * <p>{@code range} is an optional closed numeric range {@code [min, max]}. When
 * present, {@link com.enrichmeai.culvert.dataquality.DataQualityTransform} will
 * flag any value outside the range as an {@code OUT_OF_RANGE} violation —
 * no separate side-map is needed.
 *
 * @param name           The field name.
 * @param type           The wire type ({@code STRING}, {@code INT64}, etc.).
 * @param mode           {@code REQUIRED}, {@code NULLABLE}, or {@code REPEATED}.
 * @param description    Optional human description.
 * @param classification Optional sensitivity classification.
 * @param masking        Optional field-level masking policy.
 * @param range          Optional numeric bounds for range validation.
 *
 * @since Sprint 14 / T14.7 (range added)
 */
public record SchemaField(
        String name,
        String type,
        String mode,
        Optional<String> description,
        Optional<DataClassification> classification,
        Optional<MaskingPolicy> masking,
        Optional<NumericRange> range) {

    /** Canonical compact constructor — normalises nulls and validates invariants. */
    public SchemaField {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("name must be non-blank");
        }
        if (type == null || type.isBlank()) {
            throw new IllegalArgumentException("type must be non-blank");
        }
        if (mode == null) {
            mode = "NULLABLE";
        }
        if (description == null) description = Optional.empty();
        if (classification == null) classification = Optional.empty();
        if (masking == null) masking = Optional.empty();
        if (range == null) range = Optional.empty();
    }

    /**
     * Backward-compatible 6-arg constructor (no range).
     *
     * <p>Existing call sites that pass
     * {@code (name, type, mode, description, classification, masking)} continue to
     * compile and behave identically — range defaults to {@link Optional#empty()}.
     *
     * @param name           The field name.
     * @param type           The wire type.
     * @param mode           {@code REQUIRED}, {@code NULLABLE}, or {@code REPEATED}.
     * @param description    Optional human description.
     * @param classification Optional sensitivity classification.
     * @param masking        Optional field-level masking policy.
     */
    public SchemaField(
            String name,
            String type,
            String mode,
            Optional<String> description,
            Optional<DataClassification> classification,
            Optional<MaskingPolicy> masking) {
        this(name, type, mode, description, classification, masking, Optional.empty());
    }

    /**
     * Returns a copy of this field with the supplied numeric range attached.
     *
     * <p>Convenience for building a bounded field from one of the static factories:
     * <pre>{@code
     * SchemaField.required("age", "INT64").withRange(NumericRange.of(0, 150))
     * }</pre>
     *
     * @param numericRange The range to attach. Must not be {@code null}.
     * @return A new {@link SchemaField} identical to this one, with {@code range} set.
     */
    public SchemaField withRange(NumericRange numericRange) {
        if (numericRange == null) throw new IllegalArgumentException("numericRange must not be null");
        return new SchemaField(name, type, mode, description, classification, masking,
                Optional.of(numericRange));
    }

    /** Convenience: NULLABLE field with no description, classification, masking, or range. */
    public static SchemaField nullable(String name, String type) {
        return new SchemaField(name, type, "NULLABLE",
                Optional.empty(), Optional.empty(), Optional.empty(), Optional.empty());
    }

    /** Convenience: REQUIRED field with no description, classification, masking, or range. */
    public static SchemaField required(String name, String type) {
        return new SchemaField(name, type, "REQUIRED",
                Optional.empty(), Optional.empty(), Optional.empty(), Optional.empty());
    }
}
