package com.enrichmeai.culvert.dataquality;

import java.util.List;
import java.util.Objects;

/**
 * Either-style result of validating a single row against an {@code EntitySchema}.
 *
 * <p>Two sealed subtypes:
 * <ul>
 *   <li>{@link ValidRow} — every field passed all checks; carries the original row.</li>
 *   <li>{@link InvalidRow} — one or more fields failed; carries the original row and
 *       a non-empty list of {@link FieldViolation} instances (one per failing field).</li>
 * </ul>
 *
 * <p>Callers route on the type:
 * <pre>{@code
 * ValidationResult<MyRow> result = transform.validate(row);
 * if (result instanceof ValidationResult.ValidRow<MyRow> v) {
 *     successSink.write(v.row());
 * } else if (result instanceof ValidationResult.InvalidRow<MyRow> inv) {
 *     deadLetterSink.write(inv);  // passes to T14.2 dead-letter handler
 * }
 * }</pre>
 *
 * @param <R> The row type.
 *
 * @since Sprint 14 / issue #73
 */
public sealed interface ValidationResult<R>
        permits ValidationResult.ValidRow, ValidationResult.InvalidRow {

    /** The original row — present in both subtypes for symmetric access. */
    R row();

    /** Returns {@code true} iff this result is a {@link ValidRow}. */
    default boolean isValid() {
        return this instanceof ValidRow<?>;
    }

    // ------------------------------------------------------------------
    // Subtypes
    // ------------------------------------------------------------------

    /**
     * A row that passed all data-quality checks.
     *
     * @param <R> The row type.
     */
    record ValidRow<R>(R row) implements ValidationResult<R> {
        public ValidRow {
            Objects.requireNonNull(row, "row must not be null");
        }
    }

    /**
     * A row that failed one or more data-quality checks.
     *
     * <p>The {@code violations} list is guaranteed non-empty.
     *
     * @param <R> The row type.
     */
    record InvalidRow<R>(R row, List<FieldViolation> violations)
            implements ValidationResult<R> {

        public InvalidRow {
            Objects.requireNonNull(row,        "row must not be null");
            Objects.requireNonNull(violations, "violations must not be null");
            if (violations.isEmpty()) {
                throw new IllegalArgumentException(
                        "InvalidRow must have at least one FieldViolation");
            }
            violations = List.copyOf(violations);
        }
    }
}
