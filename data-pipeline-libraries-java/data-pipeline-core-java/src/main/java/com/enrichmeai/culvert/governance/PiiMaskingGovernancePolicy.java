package com.enrichmeai.culvert.governance;

import com.enrichmeai.culvert.contracts.GovernancePolicy;

import java.util.Collections;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * A structural {@link GovernancePolicy} that identifies PII fields by
 * column-name membership and/or regex pattern matching, then applies a
 * configured {@link MaskingPolicy}.
 *
 * <h2>Matching rules (applied in order; first match wins)</h2>
 * <ol>
 *   <li><strong>Column-name set</strong> — exact, case-sensitive comparison
 *       against the {@code piiColumns} set supplied at construction. E.g.
 *       {@code {"email", "ssn", "phone"}}.</li>
 *   <li><strong>Regex patterns</strong> — each pattern in {@code piiPatterns}
 *       is tested with {@link java.util.regex.Matcher#matches()} (full-field-name
 *       match). E.g. {@code [".*_pii$", ".*_secret$"]}.</li>
 * </ol>
 *
 * <p>A field that matches either rule is classified as
 * {@link DataClassification#RESTRICTED}; all other fields are
 * {@link DataClassification#INTERNAL}.
 *
 * <h2>Masking policy resolution</h2>
 * <p>When a field matches:
 * <ol>
 *   <li>If the optional {@code columnOverrides} map contains an entry for that
 *       field name, that {@link MaskingPolicy} is used.</li>
 *   <li>Otherwise the {@code defaultMaskingPolicy} is used.</li>
 * </ol>
 * The {@code columnOverrides} map only overrides the <em>policy</em> for
 * already-matched fields; a key present only in the override map (not in the
 * column set and not matching any pattern) does NOT by itself make a field
 * match. Column matching and policy selection are independent.
 *
 * <h2>Scope cap</h2>
 * <p>This implementation is <strong>structural only</strong>: it inspects
 * field names, not field values. Tag-based policy resolution (Dataplex tags,
 * Cloud DLP per-cell inspection, Purview sensitivity labels) is explicitly
 * <strong>out of scope</strong>. Those paths require a cloud SDK and belong in
 * a separate implementation. Do not add them here.
 *
 * <h2>Zero cloud / Beam imports</h2>
 * <p>This class imports only {@code java.*} and {@code com.enrichmeai.culvert.*}.
 * CI asserts this invariant via an import-line grep (see
 * {@code PiiMaskingGovernancePolicyTest}).
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
 *         .piiColumns(Set.of("email", "ssn", "phone"))
 *         .piiPatterns(List.of(".*_pii$", ".*_secret$"))
 *         .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
 *         .columnOverride("phone", new MaskingPolicy(MaskingStrategy.PARTIAL, "*", ""))
 *         .build();
 *
 * // Or pass directly to DataQualityTransform:
 * DataQualityTransform<Map<String, Object>> dq =
 *         new DataQualityTransform<>(schema, Function.identity(), policy);
 * }</pre>
 *
 * @since Sprint 14 / T14.4 / issue #76
 */
public final class PiiMaskingGovernancePolicy implements GovernancePolicy {

    private final Set<String>       piiColumns;
    private final List<Pattern>     compiledPatterns;
    private final MaskingPolicy     defaultMaskingPolicy;
    private final Map<String, MaskingPolicy> columnOverrides;

    // -----------------------------------------------------------------------
    // Constructor (use builder for readability)
    // -----------------------------------------------------------------------

    /**
     * Creates a new policy.
     *
     * @param piiColumns           Exact column names that are PII.
     *                             Case-sensitive. May be empty.
     * @param piiPatterns          Regex patterns tested against field names
     *                             (full match via {@code matches()}). May be
     *                             empty. Compiled once at construction time.
     * @param defaultMaskingPolicy The masking policy applied when a field
     *                             matches and no per-column override exists.
     *                             Must not be null.
     * @param columnOverrides      Optional per-column policy overrides.
     *                             Only applied to <em>matched</em> fields.
     *                             May be null or empty.
     * @throws NullPointerException     if any of the required args is null.
     * @throws java.util.regex.PatternSyntaxException if any pattern is invalid.
     */
    public PiiMaskingGovernancePolicy(
            Set<String>              piiColumns,
            List<String>             piiPatterns,
            MaskingPolicy            defaultMaskingPolicy,
            Map<String, MaskingPolicy> columnOverrides) {

        Objects.requireNonNull(piiColumns,           "piiColumns must not be null");
        Objects.requireNonNull(piiPatterns,          "piiPatterns must not be null");
        Objects.requireNonNull(defaultMaskingPolicy, "defaultMaskingPolicy must not be null");

        this.piiColumns           = Set.copyOf(piiColumns);
        this.compiledPatterns     = piiPatterns.stream()
                                        .map(Pattern::compile)
                                        .collect(Collectors.toUnmodifiableList());
        this.defaultMaskingPolicy = defaultMaskingPolicy;
        this.columnOverrides      = (columnOverrides != null)
                ? Map.copyOf(columnOverrides)
                : Collections.emptyMap();
    }

    // -----------------------------------------------------------------------
    // GovernancePolicy implementation
    // -----------------------------------------------------------------------

    /**
     * Returns {@link DataClassification#RESTRICTED} for any field whose name
     * is in the PII column set or matches one of the regex patterns;
     * {@link DataClassification#INTERNAL} otherwise.
     *
     * @param field The field name. Must not be null.
     * @param table The table/entity name. Accepted but not used for
     *              structural matching (reserved for future tag-based
     *              delegation).
     * @return {@code RESTRICTED} or {@code INTERNAL}.
     */
    @Override
    public DataClassification classify(String field, String table) {
        return isPii(field) ? DataClassification.RESTRICTED : DataClassification.INTERNAL;
    }

    /**
     * Returns the masking policy for {@code field}, or {@link Optional#empty()}
     * if the field is not PII.
     *
     * <p>When a field matches, the per-column override (if present) takes
     * precedence over the default masking policy.
     *
     * @param field The field name. Must not be null.
     * @param table The table/entity name (not used for structural matching).
     * @return The resolved {@link MaskingPolicy}, or empty.
     */
    @Override
    public Optional<MaskingPolicy> maskingFor(String field, String table) {
        if (!isPii(field)) return Optional.empty();
        MaskingPolicy override = columnOverrides.get(field);
        return Optional.of(override != null ? override : defaultMaskingPolicy);
    }

    /**
     * Returns {@link Optional#empty()} — this policy does not manage retention.
     */
    @Override
    public Optional<com.enrichmeai.culvert.governance.RetentionPolicy> retentionFor(String table) {
        return Optional.empty();
    }

    // -----------------------------------------------------------------------
    // Accessors (for tests and composition)
    // -----------------------------------------------------------------------

    /** Returns an unmodifiable view of the explicit PII column-name set. */
    public Set<String> getPiiColumns() {
        return piiColumns;
    }

    /** Returns the default masking policy. */
    public MaskingPolicy getDefaultMaskingPolicy() {
        return defaultMaskingPolicy;
    }

    /** Returns an unmodifiable view of the per-column override map. */
    public Map<String, MaskingPolicy> getColumnOverrides() {
        return columnOverrides;
    }

    // -----------------------------------------------------------------------
    // Internal: shared match predicate
    // -----------------------------------------------------------------------

    /**
     * Returns {@code true} iff {@code fieldName} is in the explicit column set
     * <em>or</em> matches at least one compiled regex pattern.
     *
     * <p>This is the single source of truth for both {@link #classify} and
     * {@link #maskingFor} — keeping both methods consistent by construction.
     */
    private boolean isPii(String fieldName) {
        if (piiColumns.contains(fieldName)) return true;
        for (Pattern p : compiledPatterns) {
            if (p.matcher(fieldName).matches()) return true;
        }
        return false;
    }

    // -----------------------------------------------------------------------
    // Builder
    // -----------------------------------------------------------------------

    /** Returns a new builder for {@link PiiMaskingGovernancePolicy}. */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Fluent builder for {@link PiiMaskingGovernancePolicy}.
     *
     * <p>All fields are optional except {@code defaultMaskingPolicy}, which
     * must be set before calling {@link #build()}.
     */
    public static final class Builder {

        private Set<String>                piiColumns           = Collections.emptySet();
        private List<String>               piiPatterns          = Collections.emptyList();
        private MaskingPolicy              defaultMaskingPolicy = null;
        private final Map<String, MaskingPolicy> columnOverrides =
                new java.util.LinkedHashMap<>();

        private Builder() {}

        /** Sets the explicit PII column-name set (exact, case-sensitive). */
        public Builder piiColumns(Set<String> columns) {
            this.piiColumns = Objects.requireNonNull(columns, "columns must not be null");
            return this;
        }

        /** Sets the regex pattern list matched against field names. */
        public Builder piiPatterns(List<String> patterns) {
            this.piiPatterns = Objects.requireNonNull(patterns, "patterns must not be null");
            return this;
        }

        /** Sets the default masking policy (required). */
        public Builder defaultMaskingPolicy(MaskingPolicy policy) {
            this.defaultMaskingPolicy = Objects.requireNonNull(policy, "policy must not be null");
            return this;
        }

        /** Adds a per-column override entry. */
        public Builder columnOverride(String column, MaskingPolicy policy) {
            columnOverrides.put(
                    Objects.requireNonNull(column, "column must not be null"),
                    Objects.requireNonNull(policy, "policy must not be null"));
            return this;
        }

        /** Builds the policy. Throws if {@code defaultMaskingPolicy} was not set. */
        public PiiMaskingGovernancePolicy build() {
            if (defaultMaskingPolicy == null) {
                throw new IllegalStateException("defaultMaskingPolicy must be set");
            }
            return new PiiMaskingGovernancePolicy(
                    piiColumns, piiPatterns, defaultMaskingPolicy,
                    columnOverrides.isEmpty() ? null : Map.copyOf(columnOverrides));
        }
    }
}
