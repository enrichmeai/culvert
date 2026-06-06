package com.enrichmeai.culvert.governance;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link PiiMaskingGovernancePolicy}.
 *
 * <p>Covers the six DoD boxes from issue #76:
 * <ol>
 *   <li>Column-name match → field is masked with the configured policy.</li>
 *   <li>Regex-pattern match → field is masked.</li>
 *   <li>Neither match → field passes through unmasked ({@code maskingFor} returns empty).</li>
 *   <li>Per-column override takes precedence over the default.</li>
 *   <li>{@code classify} returns RESTRICTED for matched fields, INTERNAL otherwise.</li>
 *   <li>No GCP SDK / Cloud DLP / Dataplex / tag-resolution imports (source-grep guard).</li>
 * </ol>
 *
 * @since Sprint 14 / T14.4 / issue #76
 */
class PiiMaskingGovernancePolicyTest {

    // -----------------------------------------------------------------------
    // Shared policy fixture
    // -----------------------------------------------------------------------

    private static PiiMaskingGovernancePolicy defaultPolicy() {
        return PiiMaskingGovernancePolicy.builder()
                .piiColumns(Set.of("email", "ssn", "phone"))
                .piiPatterns(List.of(".*_pii$", ".*_secret$"))
                .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
                .build();
    }

    // -----------------------------------------------------------------------
    // DoD Box 1 — column-name match is masked
    // -----------------------------------------------------------------------

    @Test
    void column_name_in_set_returns_masking_policy() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        Optional<MaskingPolicy> result = policy.maskingFor("email", "users");

        assertThat(result).isPresent();
        assertThat(result.get().strategy()).isEqualTo(MaskingStrategy.FULL);
        assertThat(result.get().replacement()).isEqualTo("***");
    }

    @Test
    void all_explicit_columns_return_masking_policy() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.maskingFor("email", "users")).isPresent();
        assertThat(policy.maskingFor("ssn",   "users")).isPresent();
        assertThat(policy.maskingFor("phone", "users")).isPresent();
    }

    @Test
    void column_name_match_is_case_sensitive() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        // "Email" (capital E) is NOT in the set {"email"} — must not match
        assertThat(policy.maskingFor("Email", "users")).isEmpty();
    }

    // -----------------------------------------------------------------------
    // DoD Box 2 — regex pattern match is masked
    // -----------------------------------------------------------------------

    @Test
    void field_matching_regex_pattern_returns_masking_policy() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.maskingFor("customer_pii", "orders")).isPresent();
        assertThat(policy.maskingFor("api_secret",   "config")).isPresent();
    }

    @Test
    void regex_is_full_match_not_partial_match() {
        // "email_pii_extra" does NOT end with "_pii" exactly (.*_pii$ requires
        // the string to END with _pii).
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        // "prefix_pii" → ends with _pii → should match
        assertThat(policy.maskingFor("prefix_pii", "t")).isPresent();

        // "pii_field" → does NOT end with _pii → should NOT match by that pattern
        // (and "pii_field" is not in the column set either)
        assertThat(policy.maskingFor("pii_field", "t")).isEmpty();
    }

    // -----------------------------------------------------------------------
    // DoD Box 3 — non-matching field passes through
    // -----------------------------------------------------------------------

    @Test
    void non_pii_field_returns_empty_masking_policy() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.maskingFor("amount",      "orders")).isEmpty();
        assertThat(policy.maskingFor("description", "products")).isEmpty();
        assertThat(policy.maskingFor("id",          "users")).isEmpty();
    }

    // -----------------------------------------------------------------------
    // DoD Box 4 — per-column override takes precedence
    // -----------------------------------------------------------------------

    @Test
    void column_override_takes_precedence_over_default() {
        MaskingPolicy defaultPolicy = new MaskingPolicy(MaskingStrategy.FULL, "***", "");
        MaskingPolicy phoneOverride = new MaskingPolicy(MaskingStrategy.PARTIAL, "*", "");

        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .piiColumns(Set.of("email", "phone"))
                .defaultMaskingPolicy(defaultPolicy)
                .columnOverride("phone", phoneOverride)
                .build();

        // "email" gets the default
        Optional<MaskingPolicy> emailPolicy = policy.maskingFor("email", "users");
        assertThat(emailPolicy).isPresent();
        assertThat(emailPolicy.get().strategy()).isEqualTo(MaskingStrategy.FULL);
        assertThat(emailPolicy.get().replacement()).isEqualTo("***");

        // "phone" gets the override
        Optional<MaskingPolicy> phonePolicy = policy.maskingFor("phone", "users");
        assertThat(phonePolicy).isPresent();
        assertThat(phonePolicy.get().strategy()).isEqualTo(MaskingStrategy.PARTIAL);
        assertThat(phonePolicy.get().replacement()).isEqualTo("*");
    }

    @Test
    void override_only_applies_to_matched_fields() {
        // A column override for "amount" (which is NOT in the column set and
        // does NOT match any regex) must NOT cause "amount" to be treated as PII.
        MaskingPolicy defaultPolicy = new MaskingPolicy(MaskingStrategy.FULL, "***", "");
        MaskingPolicy overridePolicy = new MaskingPolicy(MaskingStrategy.HASH, "*", "salt");

        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .piiColumns(Set.of("email"))
                .defaultMaskingPolicy(defaultPolicy)
                .columnOverride("amount", overridePolicy)   // not a PII column
                .build();

        // "amount" is NOT PII — override does not expand the match set
        assertThat(policy.maskingFor("amount", "orders")).isEmpty();
        assertThat(policy.classify("amount", "orders")).isEqualTo(DataClassification.INTERNAL);
    }

    // -----------------------------------------------------------------------
    // DoD Box 5 — classify returns RESTRICTED / INTERNAL correctly
    // -----------------------------------------------------------------------

    @Test
    void classify_returns_restricted_for_matched_fields() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.classify("email",       "users")).isEqualTo(DataClassification.RESTRICTED);
        assertThat(policy.classify("ssn",         "users")).isEqualTo(DataClassification.RESTRICTED);
        assertThat(policy.classify("my_pii",      "t")).isEqualTo(DataClassification.RESTRICTED);
        assertThat(policy.classify("api_secret",  "t")).isEqualTo(DataClassification.RESTRICTED);
    }

    @Test
    void classify_returns_internal_for_non_pii_fields() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.classify("amount",      "orders")).isEqualTo(DataClassification.INTERNAL);
        assertThat(policy.classify("description", "items")).isEqualTo(DataClassification.INTERNAL);
    }

    @Test
    void classify_and_maskingFor_are_consistent() {
        // If classify says RESTRICTED, maskingFor must be non-empty, and vice-versa.
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        for (String field : List.of("email", "ssn", "customer_pii", "amount", "id")) {
            boolean isRestricted =
                    policy.classify(field, "t") == DataClassification.RESTRICTED;
            boolean hasMaskingPolicy = policy.maskingFor(field, "t").isPresent();
            assertThat(isRestricted)
                    .as("classify and maskingFor disagree for field '%s'", field)
                    .isEqualTo(hasMaskingPolicy);
        }
    }

    // -----------------------------------------------------------------------
    // retention_for returns empty (no retention in PII policy)
    // -----------------------------------------------------------------------

    @Test
    void retention_for_always_returns_empty() {
        PiiMaskingGovernancePolicy policy = defaultPolicy();

        assertThat(policy.retentionFor("users")).isEmpty();
        assertThat(policy.retentionFor("any_table")).isEmpty();
    }

    // -----------------------------------------------------------------------
    // Builder validation
    // -----------------------------------------------------------------------

    @Test
    void builder_requires_default_masking_policy() {
        assertThatThrownBy(() ->
                PiiMaskingGovernancePolicy.builder()
                        .piiColumns(Set.of("email"))
                        .build())
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("defaultMaskingPolicy");
    }

    @Test
    void empty_column_set_and_empty_patterns_match_nothing() {
        PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
                .defaultMaskingPolicy(MaskingPolicy.of(MaskingStrategy.FULL))
                .build();

        assertThat(policy.maskingFor("email", "users")).isEmpty();
        assertThat(policy.classify("ssn", "users")).isEqualTo(DataClassification.INTERNAL);
    }

    // -----------------------------------------------------------------------
    // DoD Box 6 — import safety: no GCP / Beam / DLP / Dataplex imports
    // -----------------------------------------------------------------------

    @Test
    void pii_masking_policy_has_no_cloud_or_beam_imports() throws Exception {
        // CWD for surefire is the module directory
        // (data-pipeline-libraries-java/data-pipeline-core-java).
        Path src = Paths.get(
                "src/main/java/com/enrichmeai/culvert/governance/PiiMaskingGovernancePolicy.java");
        List<String> importLines = Files.lines(src)
                .filter(line -> line.startsWith("import "))
                .collect(java.util.stream.Collectors.toList());

        for (String importLine : importLines) {
            assertThat(importLine)
                    .as("PiiMaskingGovernancePolicy must not import com.google.cloud.*")
                    .doesNotContain("com.google.cloud");
            assertThat(importLine)
                    .as("PiiMaskingGovernancePolicy must not import org.apache.beam.*")
                    .doesNotContain("org.apache.beam");
            assertThat(importLine)
                    .as("PiiMaskingGovernancePolicy must not import com.google.privacy.dlp.*")
                    .doesNotContain("com.google.privacy.dlp");
            assertThat(importLine)
                    .as("PiiMaskingGovernancePolicy must not import com.google.cloud.dataplex.*")
                    .doesNotContain("dataplex");
        }
    }

    @Test
    void masker_has_no_cloud_or_beam_imports() throws Exception {
        Path src = Paths.get(
                "src/main/java/com/enrichmeai/culvert/governance/Masker.java");
        List<String> importLines = Files.lines(src)
                .filter(line -> line.startsWith("import "))
                .collect(java.util.stream.Collectors.toList());

        for (String importLine : importLines) {
            assertThat(importLine)
                    .as("Masker must not import com.google.cloud.*")
                    .doesNotContain("com.google.cloud");
            assertThat(importLine)
                    .as("Masker must not import org.apache.beam.*")
                    .doesNotContain("org.apache.beam");
            assertThat(importLine)
                    .as("Masker must not import DLP")
                    .doesNotContain("com.google.privacy.dlp");
        }
    }
}
