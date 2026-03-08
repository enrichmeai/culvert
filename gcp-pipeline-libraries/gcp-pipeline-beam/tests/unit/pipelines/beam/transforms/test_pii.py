"""
Unit tests for MaskPIIDoFn — PII masking transforms.

Good-practice patterns demonstrated here:
- No module-level sys.modules patching (causes global state contamination)
- Real apache_beam imports; mock only at method scope when needed
- Fixtures for schema construction — DRY, reusable, clearly named
- Descriptive test names following Given/When/Then comment structure
- Boundary tests for each masking strategy (SSN, EMAIL, FULL, REDACTED, PARTIAL)
- Edge cases: None values, missing fields, no PII fields defined
"""

import pytest

from gcp_pipeline_beam.pipelines.beam.transforms.pii import MaskPIIDoFn
from gcp_pipeline_core.schema import EntitySchema, SchemaField


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pii_schema() -> EntitySchema:
    """Schema with one field per supported PII masking strategy."""
    return EntitySchema(
        entity_name="test_entity",
        system_id="test_sys",
        fields=[
            SchemaField(name="id", field_type="STRING", required=True),
            SchemaField(name="email", field_type="STRING", is_pii=True, pii_type="EMAIL"),
            SchemaField(name="ssn", field_type="STRING", is_pii=True, pii_type="SSN"),
            SchemaField(name="full_mask", field_type="STRING", is_pii=True, pii_type="FULL"),
            SchemaField(name="redacted", field_type="STRING", is_pii=True, pii_type="REDACTED"),
            SchemaField(name="partial", field_type="STRING", is_pii=True, pii_type="PARTIAL"),
            SchemaField(name="default_pii", field_type="STRING", is_pii=True),  # pii_type omitted
        ],
        primary_key=["id"],
    )


@pytest.fixture
def no_pii_schema() -> EntitySchema:
    """Schema with no PII fields — masking should be a no-op."""
    return EntitySchema(
        entity_name="clean_entity",
        system_id="sys",
        fields=[SchemaField(name="id", field_type="STRING", required=True)],
        primary_key=["id"],
    )


def _make_dofn(schema: EntitySchema) -> MaskPIIDoFn:
    """Construct and initialise a MaskPIIDoFn (calls setup() as Beam would)."""
    do_fn = MaskPIIDoFn(schema)
    do_fn.setup()
    return do_fn


# ---------------------------------------------------------------------------
# Masking strategy tests
# ---------------------------------------------------------------------------


class TestMaskingStrategies:
    """Verify each pii_type applies the correct masking transformation."""

    def test_email_masks_local_part(self, pii_schema):
        """Given an email address, only the local part should be masked."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "email": "user@example.com"}

        (result,) = do_fn.process(record)

        assert result["email"] == "****@example.com"

    def test_ssn_exposes_last_four_digits(self, pii_schema):
        """Given a 9-digit SSN, format should be XXX-XX-<last4>."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "ssn": "123456789"}

        (result,) = do_fn.process(record)

        assert result["ssn"] == "XXX-XX-6789"

    def test_ssn_short_value_falls_back_safely(self, pii_schema):
        """Given a SSN shorter than 4 chars, fallback should not raise."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "ssn": "123"}

        (result,) = do_fn.process(record)

        assert result["ssn"] == "XXX-XX-****"

    def test_full_masks_all_characters(self, pii_schema):
        """FULL strategy should replace every character with an asterisk."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "full_mask": "secret"}

        (result,) = do_fn.process(record)

        assert result["full_mask"] == "******"

    def test_redacted_replaces_with_literal(self, pii_schema):
        """REDACTED strategy should replace the value with the literal 'REDACTED'."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "redacted": "top_secret_value"}

        (result,) = do_fn.process(record)

        assert result["redacted"] == "REDACTED"

    def test_partial_exposes_last_four_characters(self, pii_schema):
        """PARTIAL strategy should mask all but the last 4 characters."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "partial": "123456789"}

        (result,) = do_fn.process(record)

        assert result["partial"] == "*****6789"

    def test_partial_short_value_returns_four_stars(self, pii_schema):
        """PARTIAL on a value <= 4 chars should return '****'."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "partial": "abc"}

        (result,) = do_fn.process(record)

        assert result["partial"] == "****"

    def test_unknown_pii_type_falls_back_to_partial_mask(self, pii_schema):
        """Fields marked is_pii=True without pii_type default to partial masking."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "default_pii": "987654321"}

        (result,) = do_fn.process(record)

        assert result["default_pii"] == "*****4321"

    def test_non_pii_fields_are_passed_through_unchanged(self, pii_schema):
        """Fields not flagged as PII must not be altered."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "email": "a@b.com", "non_pii_field": "safe_value"}

        (result,) = do_fn.process(record)

        assert result["non_pii_field"] == "safe_value"

    def test_id_field_is_never_masked(self, pii_schema):
        """Primary key field (not PII) must always pass through unchanged."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "12345", "email": "u@example.com"}

        (result,) = do_fn.process(record)

        assert result["id"] == "12345"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: None values, missing PII fields, no-PII schema."""

    def test_none_pii_value_is_passed_through_as_none(self, pii_schema):
        """
        Given a PII field containing None,
        masking must not raise and the value must remain None.
        """
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "email": None}

        (result,) = do_fn.process(record)

        assert result["email"] is None

    def test_missing_pii_field_in_record_is_skipped_silently(self, pii_schema):
        """
        Given a record that omits a PII field,
        the DoFn must not raise a KeyError.
        """
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1"}  # 'email', 'ssn', etc. all absent

        (result,) = do_fn.process(record)

        assert result == {"id": "1"}

    def test_no_pii_schema_returns_record_unchanged(self, no_pii_schema):
        """
        Given a schema with no PII fields,
        the DoFn must be a pure pass-through (no copies, no modifications).
        """
        do_fn = _make_dofn(no_pii_schema)
        record = {"id": "999", "data": "untouched"}

        (result,) = do_fn.process(record)

        assert result == record

    def test_email_without_at_sign_falls_back_to_placeholder(self, pii_schema):
        """Given a malformed email (no @), masking should not raise."""
        do_fn = _make_dofn(pii_schema)
        record = {"id": "1", "email": "not_an_email"}

        (result,) = do_fn.process(record)

        assert result["email"] == "****@****.***"

    def test_all_pii_strategies_in_one_record(self, pii_schema):
        """Integration: a single record with all PII field types is masked correctly."""
        do_fn = _make_dofn(pii_schema)
        record = {
            "id": "123",
            "email": "user@example.com",
            "ssn": "123456789",
            "full_mask": "secret",
            "redacted": "top_secret",
            "partial": "123456789",
            "default_pii": "987654321",
        }

        (result,) = do_fn.process(record)

        assert result["id"] == "123"
        assert result["email"] == "****@example.com"
        assert result["ssn"] == "XXX-XX-6789"
        assert result["full_mask"] == "******"
        assert result["redacted"] == "REDACTED"
        assert result["partial"] == "*****6789"
        assert result["default_pii"] == "*****4321"
