package com.enrichmeai.culvert.dataquality;

import java.util.Objects;

/**
 * A closed numeric range {@code [min, max]} used by {@link DataQualityTransform}
 * to detect out-of-range field values.
 *
 * <p>Both bounds are inclusive. Supply a {@code Map<String, NumericRange>} to
 * {@link DataQualityTransform#DataQualityTransform(com.enrichmeai.culvert.schema.EntitySchema,
 * java.util.function.Function, java.util.Map)} to opt a specific field into range
 * validation. Fields without an entry are not range-checked.
 *
 * @param min The inclusive lower bound.
 * @param max The inclusive upper bound (must be ≥ {@code min}).
 *
 * @since Sprint 14 / issue #73
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
