"""Tests for the governance_api concretes: Masker (mask()) + PiiMaskingGovernancePolicy.

Mirrors behavioural coverage from Java:
  - Masker.java (Sprint 14 / T14.4)
  - PiiMaskingGovernancePolicy.java (Sprint 14 / T14.4 / issue #76)

DoD requirement (T18.3): all new tests must pass within the full suite run.
"""

from __future__ import annotations

import hashlib

import pytest

from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.masker import _DEFAULT_SALT, mask
from data_pipeline_core.governance_api.pii_masking_governance_policy import (
    PiiMaskingGovernancePolicy,
)
from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy


# ===========================================================================
# Masker (mask()) — mirrors Masker.java strategy helpers
# ===========================================================================

class TestMaskNone:
    """NONE strategy passes value through unchanged (Masker.java:59)."""

    def test_none_strategy_string(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.NONE)
        assert mask("hello", p) == "hello"

    def test_none_strategy_int(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.NONE)
        assert mask(42, p) == 42

    def test_null_passthrough(self) -> None:
        """None value is returned unchanged regardless of strategy."""
        p = MaskingPolicy(strategy=MaskingStrategy.FULL)
        assert mask(None, p) is None

    def test_policy_none_raises(self) -> None:
        with pytest.raises(TypeError):
            mask("x", None)  # type: ignore[arg-type]


class TestMaskFull:
    """FULL strategy replaces value with policy.replacement (Masker.java:60)."""

    def test_default_replacement(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.FULL)
        assert mask("secret", p) == "*"

    def test_custom_replacement(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="***")
        assert mask("secret", p) == "***"

    def test_non_string_value(self) -> None:
        """FULL replaces the *replacement* string, not the original type."""
        p = MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="REDACTED")
        assert mask(12345, p) == "REDACTED"


class TestMaskRedacted:
    """REDACTED behaves identically to FULL (Masker.java:60)."""

    def test_redacted_equals_full(self) -> None:
        p_full = MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="***")
        p_red = MaskingPolicy(strategy=MaskingStrategy.REDACTED, replacement="***")
        assert mask("value", p_full) == mask("value", p_red)


class TestMaskPartial:
    """PARTIAL keeps last 4 characters (Masker.java:74-81)."""

    def test_long_string_keeps_last_4(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        result = mask("4111111111111234", p)
        assert result == "************1234"

    def test_exactly_4_chars_all_replaced(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        assert mask("1234", p) == "****"

    def test_fewer_than_4_chars_all_replaced(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        assert mask("ab", p) == "**"

    def test_custom_replacement_char(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL, replacement="X")
        result = mask("abcde12345", p)
        # last 4 = "2345", rest = "XXXXXX"
        assert result == "XXXXXX2345"

    def test_empty_replacement_defaults_to_star(self) -> None:
        """Empty replacement → '*' (mirrors Masker.java:75: replChar = '*')."""
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL, replacement="")
        result = mask("abcde", p)
        # "abcde" is 5 chars; last 4 kept → "bcde"; first char masked → "*bcde"
        assert result == "*bcde"

    def test_non_string_converted_via_str(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        # int 123456 → str "123456" → last 4 kept
        result = mask(123456, p)
        assert result == "**3456"


class TestMaskHash:
    """HASH produces deterministic SHA-256 (Masker.java:87-101)."""

    def test_hash_deterministic(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="mysalt")
        assert mask("alice@example.com", p) == mask("alice@example.com", p)

    def test_hash_default_salt(self) -> None:
        """Empty salt uses DEFAULT_SALT = 'culvert-pii-salt' (Masker.java:41)."""
        p = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="")
        value = "test-value"
        expected = hashlib.sha256(
            (_DEFAULT_SALT + value).encode("utf-8")
        ).hexdigest()
        assert mask(value, p) == expected

    def test_hash_custom_salt(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="abc")
        value = "test"
        expected = hashlib.sha256(("abc" + value).encode("utf-8")).hexdigest()
        assert mask(value, p) == expected

    def test_different_values_produce_different_hashes(self) -> None:
        p = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="s")
        assert mask("alice", p) != mask("bob", p)

    def test_different_salts_produce_different_hashes(self) -> None:
        p1 = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="s1")
        p2 = MaskingPolicy(strategy=MaskingStrategy.HASH, salt="s2")
        assert mask("same-value", p1) != mask("same-value", p2)


# ===========================================================================
# PiiMaskingGovernancePolicy
# ===========================================================================

@pytest.fixture
def default_policy() -> MaskingPolicy:
    return MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="***")


@pytest.fixture
def pii_policy(default_policy: MaskingPolicy) -> PiiMaskingGovernancePolicy:
    return PiiMaskingGovernancePolicy(
        pii_columns={"email", "ssn", "phone"},
        pii_patterns=[".*_pii$", ".*_secret$"],
        default_masking_policy=default_policy,
    )


class TestPiiMaskingGovernancePolicyConstruction:
    def test_requires_default_masking_policy(self) -> None:
        with pytest.raises(ValueError, match="default_masking_policy"):
            PiiMaskingGovernancePolicy(
                pii_columns={"email"},
                default_masking_policy=None,  # type: ignore[arg-type]
            )

    def test_empty_columns_and_patterns_valid(self, default_policy: MaskingPolicy) -> None:
        p = PiiMaskingGovernancePolicy(default_masking_policy=default_policy)
        assert p.classify("any_field", "any_table") is DataClassification.INTERNAL

    def test_invalid_regex_raises(self, default_policy: MaskingPolicy) -> None:
        import re
        with pytest.raises(re.error):
            PiiMaskingGovernancePolicy(
                pii_patterns=["[invalid"],
                default_masking_policy=default_policy,
            )


class TestPiiMaskingGovernancePolicyClassify:
    """classify() mirrors PiiMaskingGovernancePolicy.java:137-139."""

    def test_exact_column_classified_restricted(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert pii_policy.classify("email", "users") is DataClassification.RESTRICTED

    def test_pattern_column_classified_restricted(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert pii_policy.classify("national_id_pii", "users") is DataClassification.RESTRICTED

    def test_non_pii_classified_internal(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert pii_policy.classify("first_name", "users") is DataClassification.INTERNAL

    def test_case_sensitive_match(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        """Column matching is case-sensitive (mirrors Java Set.contains)."""
        assert pii_policy.classify("Email", "users") is DataClassification.INTERNAL

    def test_table_arg_ignored_for_structural_match(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        """table is accepted but not used — both calls return the same result."""
        assert pii_policy.classify("email", "table_a") == pii_policy.classify("email", "table_b")


class TestPiiMaskingGovernancePolicyMaskingFor:
    """masking_for() mirrors PiiMaskingGovernancePolicy.java:152-157."""

    def test_pii_column_returns_default_policy(
        self, pii_policy: PiiMaskingGovernancePolicy, default_policy: MaskingPolicy
    ) -> None:
        result = pii_policy.masking_for("email", "users")
        assert result == default_policy

    def test_non_pii_returns_none(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert pii_policy.masking_for("first_name", "users") is None

    def test_column_override_applied(self, default_policy: MaskingPolicy) -> None:
        """Per-column override takes precedence (PiiMaskingGovernancePolicy.java:155-156)."""
        phone_policy = MaskingPolicy(strategy=MaskingStrategy.PARTIAL, replacement="*")
        p = PiiMaskingGovernancePolicy(
            pii_columns={"email", "phone"},
            default_masking_policy=default_policy,
            column_overrides={"phone": phone_policy},
        )
        assert p.masking_for("phone", "users") == phone_policy
        assert p.masking_for("email", "users") == default_policy

    def test_override_key_not_in_column_set_does_not_match(self, default_policy: MaskingPolicy) -> None:
        """Override map entry alone does not make a field match (Java doc, line ~43)."""
        override_only_policy = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        p = PiiMaskingGovernancePolicy(
            pii_columns={"email"},
            default_masking_policy=default_policy,
            column_overrides={"address": override_only_policy},  # not in pii_columns
        )
        # "address" is NOT matched — override key alone doesn't qualify the field
        assert p.masking_for("address", "users") is None

    def test_pattern_matched_field_returns_default_policy(
        self, pii_policy: PiiMaskingGovernancePolicy, default_policy: MaskingPolicy
    ) -> None:
        result = pii_policy.masking_for("credit_card_secret", "payments")
        assert result == default_policy


class TestPiiMaskingGovernancePolicyRetentionFor:
    """retention_for() always returns None (PiiMaskingGovernancePolicy.java:163-165)."""

    def test_retention_for_always_none(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert pii_policy.retention_for("users") is None
        assert pii_policy.retention_for("payments") is None


class TestPiiMaskingGovernancePolicyRegex:
    """Regex matching uses re.fullmatch (mirrors Java Matcher.matches — anchored)."""

    def test_pattern_full_match_required(self, default_policy: MaskingPolicy) -> None:
        """'_pii' suffix pattern must match the full field name."""
        p = PiiMaskingGovernancePolicy(
            pii_patterns=[".*_pii$"],
            default_masking_policy=default_policy,
        )
        assert p.classify("name_pii", "t") is DataClassification.RESTRICTED
        # Partial match — pattern ".*_pii$" would match "name_pii_extra" only
        # if fullmatch anchors; without anchoring "re.match" would pass partial
        # We test a field that should NOT match fully.
        assert p.classify("name_pii_extra_suffix", "t") is DataClassification.INTERNAL

    def test_pattern_secret_suffix(self, default_policy: MaskingPolicy) -> None:
        p = PiiMaskingGovernancePolicy(
            pii_patterns=[".*_secret$"],
            default_masking_policy=default_policy,
        )
        assert p.classify("api_secret", "t") is DataClassification.RESTRICTED
        assert p.classify("api_secret_key", "t") is DataClassification.INTERNAL


class TestPiiMaskingGovernancePolicyProtocol:
    """PiiMaskingGovernancePolicy satisfies GovernancePolicy structurally."""

    def test_isinstance_governance_policy(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        """runtime_checkable Protocol: isinstance must pass (mirrors Java implements GovernancePolicy)."""
        assert isinstance(pii_policy, GovernancePolicy)


class TestPiiMaskingGovernancePolicyAccessors:
    def test_pii_columns_accessor(self, pii_policy: PiiMaskingGovernancePolicy) -> None:
        assert "email" in pii_policy.pii_columns
        assert "ssn" in pii_policy.pii_columns

    def test_default_masking_policy_accessor(
        self, pii_policy: PiiMaskingGovernancePolicy, default_policy: MaskingPolicy
    ) -> None:
        assert pii_policy.default_masking_policy == default_policy

    def test_column_overrides_returns_copy(self, default_policy: MaskingPolicy) -> None:
        override = MaskingPolicy(strategy=MaskingStrategy.PARTIAL)
        p = PiiMaskingGovernancePolicy(
            pii_columns={"phone"},
            default_masking_policy=default_policy,
            column_overrides={"phone": override},
        )
        overrides = p.column_overrides
        assert overrides["phone"] == override
        # Mutating the returned dict must not affect the policy's internal state
        overrides["phone"] = default_policy
        assert p.column_overrides["phone"] == override
