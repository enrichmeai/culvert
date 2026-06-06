package com.enrichmeai.culvert.dataquality;

import java.util.Objects;

/**
 * A closed numeric range {@code [min, max]} used by {@link DataQualityTransform}
 * to detect out-of-range field values.
 *
 * <p>Both bounds are inclusive. Attach a {@code NumericRange} to a
 * {@link com.enrichmeai.culvert.schema.SchemaField} via
 * {@link com.enrichmeai.culvert.schema.SchemaField#withRange(NumericRange)} to opt
 * that field into range validation. {@link DataQualityTransform} reads bounds
 * directly from the schema — no separate side-map is required.
 *
 * @param min The inclusive lower bound.
 * @param max The inclusive upper bound (must be ≥ {@code min}).
 *
 * @since Sprint 14 / issue #73 (T14.1); schema-grounded T14.7 / issue #100
 */
public record NumericRange(double min, double max) {

    public NumericRange {
        if (max < min) {
            throw new IllegalArgumentException(
                    "max (" + max + ") must be >= min (" + min + ")");
        }
    }

    /** Convenience factory. */
    public static NumericRange of(double min, double max) {
        return new NumericRange(min, max);
    }

    /**
     * Returns {@code true} if {@code value} lies within {@code [min, max]} (inclusive).
     *
     * @param value The numeric value to test.
     */
    public boolean contains(double value) {
        return value >= min && value <= max;
    }
}
