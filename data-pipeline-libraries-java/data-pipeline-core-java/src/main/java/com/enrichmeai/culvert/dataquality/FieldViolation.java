package com.enrichmeai.culvert.dataquality;

import java.util.Objects;

/**
 * A single field-level violation found during data-quality validation.
 *
 * <p>Instances are produced by {@link DataQualityTransform#validate(Object)}
 * and collected into an {@link ValidationResult.InvalidRow} when one or more
 * fields fail validation.
 *
 * @param fieldName     The name of the field that failed validation.
 * @param violationKind The category of violation (see {@link ViolationKind}).
 * @param detail        A human-readable description of the violation, including
 *                      any expected and actual values.
 *
 * @since Sprint 14 / issue #73
 */
public record FieldViolation(
        String fieldName,
        ViolationKind violationKind,
        String detail) {

    public FieldViolation {
        Objects.requireNonNull(fieldName,     "fieldName must not be null");
        Objects.requireNonNull(violationKind, "violationKind must not be null");
        Objects.requireNonNull(detail,        "detail must not be null");
    }
}
