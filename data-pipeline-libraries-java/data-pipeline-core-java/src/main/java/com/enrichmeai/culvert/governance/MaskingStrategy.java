package com.enrichmeai.culvert.governance;

/**
 * How a field is masked when masking is applied.
 *
 * <p>Mirrors the Python {@code MaskingStrategy} enum. The value strings are
 * part of the contract — every adapter's PII transform implements these four
 * modes.
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
