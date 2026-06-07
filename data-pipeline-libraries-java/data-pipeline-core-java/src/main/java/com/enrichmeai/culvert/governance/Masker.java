package com.enrichmeai.culvert.governance;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Applies a {@link MaskingPolicy} to a single field value.
 *
 * <p>This is a pure-Java, cloud-neutral utility. It contains no GCP SDK,
 * Cloud DLP, Dataplex, or tag-resolution imports. All masking is structural —
 * based on field-name matching, not per-cell content inspection.
 *
 * <h2>Supported strategies</h2>
 * <ul>
 *   <li>{@link MaskingStrategy#NONE} — value is returned unchanged.</li>
 *   <li>{@link MaskingStrategy#FULL} — value is replaced with
 *       {@code policy.replacement()} (defaults to {@code "*"}).</li>
 *   <li>{@link MaskingStrategy#REDACTED} — same as FULL; value is replaced
 *       with {@code policy.replacement()}.</li>
 *   <li>{@link MaskingStrategy#PARTIAL} — all characters of the string
 *       representation are replaced with {@code policy.replacement()} except
 *       the last 4, which are kept. If the value has 4 or fewer characters
 *       all characters are replaced. Non-string values are converted via
 *       {@code toString()} first.</li>
 *   <li>{@link MaskingStrategy#HASH} — a deterministic SHA-256 hex digest
 *       of the string representation (prefixed by the salt). The salt from
 *       {@code policy.salt()} is used as-is; if empty, a constant
 *       process-stable default salt {@code "culvert-pii-salt"} is applied
 *       (full per-process salt generation is out of scope for this ticket).</li>
 * </ul>
 *
 * <p><strong>Null passthrough:</strong> if {@code value} is {@code null} the
 * method returns {@code null} regardless of strategy — nulls are not fabricated.
 *
 * @since Sprint 14 / T14.4
 */
public final class Masker {

    /** Default salt used when {@code MaskingPolicy.salt()} is empty. */
    private static final String DEFAULT_SALT = "culvert-pii-salt";

    private Masker() { /* utility class */ }

    /**
     * Applies {@code policy} to {@code value}.
     *
     * @param value  The field value to mask. May be {@code null} (returned
     *               unchanged).
     * @param policy The masking policy to apply. Must not be {@code null}.
     * @return The masked value, or {@code null} if {@code value} was null.
     * @throws NullPointerException if {@code policy} is null.
     */
    public static Object mask(Object value, MaskingPolicy policy) {
        if (policy == null) throw new NullPointerException("policy must not be null");
        if (value == null) return null;

        return switch (policy.strategy()) {
            case NONE -> value;
            case FULL, REDACTED -> policy.replacement();
            case PARTIAL -> maskPartial(value.toString(), policy.replacement());
            case HASH -> maskHash(value.toString(), policy.salt());
        };
    }

    // -----------------------------------------------------------------------
    // Strategy helpers
    // -----------------------------------------------------------------------

    /**
     * Masks all characters except the last 4, replacing them with
     * {@code replacement}.
     */
    private static String maskPartial(String s, String replacement) {
        char replChar = replacement.isEmpty() ? '*' : replacement.charAt(0);
        if (s.length() <= 4) {
            return String.valueOf(replChar).repeat(s.length());
        }
        String suffix = s.substring(s.length() - 4);
        return String.valueOf(replChar).repeat(s.length() - 4) + suffix;
    }

    /**
     * Returns a deterministic hex-encoded SHA-256 digest of
     * {@code (salt + value)}.
     */
    private static String maskHash(String value, String salt) {
        String effectiveSalt = (salt == null || salt.isEmpty()) ? DEFAULT_SALT : salt;
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(effectiveSalt.getBytes(StandardCharsets.UTF_8));
            byte[] digest = md.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 is guaranteed present in every JRE; this branch is unreachable.
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
