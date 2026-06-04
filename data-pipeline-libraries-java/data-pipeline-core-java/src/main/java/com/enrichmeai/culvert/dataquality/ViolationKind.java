package com.enrichmeai.culvert.dataquality;

/**
 * Classification of a single field violation found during data-quality validation.
 *
 * <ul>
 *   <li>{@link #MISSING_REQUIRED} — a field declared {@code REQUIRED} in the
 *       {@code EntitySchema} had a {@code null} or absent value.</li>
 *   <li>{@link #TYPE_MISMATCH} — the field's runtime value is not assignable to
 *       the Java type that corresponds to the schema wire type
 *       ({@code STRING→String}, {@code INT64→Long}, {@code FLOAT64→Double},
 *       {@code BOOL→Boolean}).</li>
 *   <li>{@link #OUT_OF_RANGE} — the field's numeric value falls outside the
 *       {@link NumericRange} that was supplied to
 *       {@link DataQualityTransform} at construction time.</li>
 * </ul>
 *
 * <p>Zero GCP / Beam dependencies — this enum lives in the cloud-neutral core.
 *
 * @since Sprint 14 / issue #73
 */
public enum ViolationKind {

    /** The field is declared REQUIRED but its value is null or missing. */
    MISSING_REQUIRED,

    /** The field's runtime value type does not match the schema-declared wire type. */
    TYPE_MISMATCH,

    /** The field's numeric value falls outside its declared {@link NumericRange}. */
    OUT_OF_RANGE
}
