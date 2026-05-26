package com.enrichmeai.culvert.schema;

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
 * @param name           The field name.
 * @param type           The wire type ({@code STRING}, {@code INT64}, etc.).
 * @param mode           {@code REQUIRED}, {@code NULLABLE}, or {@code REPEATED}.
 * @param description    Optional human description.
 * @param classification Optional sensitivity classification.
 * @param masking        Optional field-level masking policy.
 */
public record SchemaField(
        String name,
        String type,
        String mode,
        Optional<String> description,
        Optional<DataClassification> classification,
        Optional<MaskingPolicy> masking) {

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
    }

    /** Convenience: NULLABLE field with no description, classification, or masking. */
    public static SchemaField nullable(String name, String type) {
        return new SchemaField(name, type, "NULLABLE",
                Optional.empty(), Optional.empty(), Optional.empty());
    }

    /** Convenience: REQUIRED field with no description, classification, or masking. */
    public static SchemaField required(String name, String type) {
        return new SchemaField(name, type, "REQUIRED",
                Optional.empty(), Optional.empty(), Optional.empty());
    }
}
