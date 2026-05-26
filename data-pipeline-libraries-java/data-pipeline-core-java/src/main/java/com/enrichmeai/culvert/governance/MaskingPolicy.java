package com.enrichmeai.culvert.governance;

/**
 * Policy: this field is masked using this strategy.
 *
 * <p>{@code replacement} is used by {@link MaskingStrategy#FULL} and
 * {@link MaskingStrategy#REDACTED} (e.g. {@code "***"}). For
 * {@link MaskingStrategy#PARTIAL} it can be the replacement character
 * (defaults to {@code "*"}). For {@link MaskingStrategy#HASH} it is the
 * salt; if empty, a process-stable salt is generated at first use.
 *
 * <p>Mirrors the Python {@code MaskingPolicy} dataclass.
 *
 * @param strategy   The masking strategy.
 * @param replacement The replacement character/string. Defaults to {@code "*"}.
 * @param salt       Salt for {@link MaskingStrategy#HASH}. Empty string means use a process-stable salt.
 */
public record MaskingPolicy(MaskingStrategy strategy, String replacement, String salt) {

    public MaskingPolicy {
        if (strategy == null) {
            throw new IllegalArgumentException("strategy must not be null");
        }
        if (replacement == null) {
            replacement = "*";
        }
        if (salt == null) {
            salt = "";
        }
    }

    /** Convenience factory: just a strategy, defaults for replacement and salt. */
    public static MaskingPolicy of(MaskingStrategy strategy) {
        return new MaskingPolicy(strategy, "*", "");
    }
}
