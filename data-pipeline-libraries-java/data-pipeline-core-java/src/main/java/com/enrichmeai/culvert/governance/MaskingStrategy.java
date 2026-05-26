package com.enrichmeai.culvert.governance;

/**
 * How a field is masked when masking is applied.
 *
 * <p>Mirrors the Python {@code MaskingStrategy} enum. Values match the
 * transforms in the existing {@code gcp_pipeline_beam.pipelines.beam.transforms.pii}
 * module.
 */
public enum MaskingStrategy {
    /** Entire value replaced with a constant (the {@code replacement}). */
    FULL("full"),
    /** Most characters replaced, last 4 kept (the "last4" pattern). */
    PARTIAL("partial"),
    /** Value removed, sentinel returned. */
    REDACTED("redacted"),
    /** Deterministic hash. */
    HASH("hash"),
    /** Explicitly no masking. Overrides defaults. */
    NONE("none");

    private final String value;

    MaskingStrategy(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}
