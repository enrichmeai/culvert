"""Behavioral tests for dbt macros — assert on rendered SQL, not just existence.

The sibling file ``test_pii_macros.py`` runs ``dbt parse`` and checks that macros
show up in ``manifest.json``. That protects against "I deleted the file" regressions,
but it won't catch a macro that silently stops emitting the SQL we rely on (for
example, a PII mask that renders to the empty string, or an audit helper that
forgets ``processed_timestamp``).

This module fills that gap. It prefers a fresh ``dbt compile`` so assertions run
against the current macros, and falls back to the checked-in compiled artefacts
under ``target/compiled/`` when dbt isn't on PATH (e.g. slim CI containers).

Each assertion is deliberately pattern-level, not exact-string: we want the tests
to survive harmless whitespace reshuffles while still failing loudly if the
semantic SQL changes.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE / "dbt_test_project"
COMPILED_DIR = (
    PROJECT_DIR / "target" / "compiled" / "transform_unit_tests" / "models"
)


def _resolve_dbt_executable() -> str | None:
    """Return a usable dbt path, or None if dbt isn't available."""
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if any(os.access(os.path.join(p, "dbt"), os.X_OK) for p in path_dirs):
        return "dbt"
    venv_dbt = os.path.join(os.path.dirname(sys.executable), "dbt")
    if os.path.exists(venv_dbt):
        return venv_dbt
    return None


def _recompile_if_possible() -> None:
    """Best-effort ``dbt compile`` so assertions run against fresh SQL.

    We don't fail the test suite if dbt isn't installed — the checked-in
    compiled artefacts act as a golden snapshot. We *do* fail if dbt is
    present but compilation blows up, because that's a real regression.
    """
    dbt = _resolve_dbt_executable()
    if dbt is None:
        return

    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = str(PROJECT_DIR)

    result = subprocess.run(
        [
            dbt,
            "compile",
            "--project-dir",
            str(PROJECT_DIR),
            "--profiles-dir",
            str(PROJECT_DIR),
            "--target",
            "dev",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    # dbt compile can succeed without warehouse creds for these test models
    # (they ref() other in-project models, no source() calls). If it fails
    # we surface the full output so debugging isn't a guessing game.
    assert result.returncode == 0, (
        f"dbt compile failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def _read_compiled(model: str) -> str:
    path = COMPILED_DIR / f"{model}.sql"
    assert path.exists(), (
        f"Compiled SQL missing at {path}. "
        f"Run `dbt compile --project-dir {PROJECT_DIR}` to regenerate, "
        f"or install dbt so this test can regenerate it automatically."
    )
    return path.read_text()


def _normalise(sql: str) -> str:
    """Collapse whitespace so pattern matches aren't fragile."""
    return re.sub(r"\s+", " ", sql).strip()


@pytest.fixture(scope="module", autouse=True)
def _compile_once():
    _recompile_if_possible()
    yield


# ---------------------------------------------------------------------------
# PII masking — pii_masking.sql
# ---------------------------------------------------------------------------


class TestPiiMasks:
    """One test per mask strategy so failures point at the exact macro."""

    @pytest.fixture(scope="class")
    def sql(self) -> str:
        return _normalise(_read_compiled("test_pii_output"))

    def test_mask_with_suffix_keeps_last_four(self, sql: str) -> None:
        # mask_with_suffix('ssn') → prefix 'XXX-XX-' + last 4 chars
        assert "CONCAT('XXX-XX-'" in sql
        assert "SUBSTRING(CAST(ssn AS STRING), -4)" in sql

    def test_mask_full_uses_rpad_over_length(self, sql: str) -> None:
        # mask_full('ssn') → RPAD('', LENGTH(...), '*'); fully redacts
        assert "RPAD('', LENGTH(CAST(ssn AS STRING)), '*')" in sql

    def test_mask_partial_last4_preserves_short_values(self, sql: str) -> None:
        # Short strings (<=4 chars) are passed through unmasked so we don't
        # expose more than we would have anyway. Longer values mask the
        # front and keep the last 4.
        assert "LENGTH(CAST(account_number AS STRING)) <= 4" in sql
        assert "SUBSTRING(CAST(account_number AS STRING), -4)" in sql

    def test_mask_email_keeps_domain(self, sql: str) -> None:
        # Local-part replaced with '****', domain preserved via POSITION('@' IN ...)
        assert "'****'" in sql
        assert "POSITION('@' IN CAST(email AS STRING))" in sql

    def test_mask_phone_generic_keeps_area_and_last4(self, sql: str) -> None:
        # Keep first 3 (area code) and last 4, middle becomes '-***-'
        assert "SUBSTRING(CAST(phone AS STRING), 1, 3)" in sql
        assert "'-***-'" in sql
        assert "SUBSTRING(CAST(phone AS STRING), -4)" in sql

    def test_mask_partial_first1_keeps_initial(self, sql: str) -> None:
        # Names: keep first char, mask the rest with '*'
        assert "SUBSTRING(CAST(first_name AS STRING), 1, 1)" in sql
        assert "RPAD('', LENGTH(CAST(first_name AS STRING)) - 1, '*')" in sql

    def test_null_inputs_stay_null(self, sql: str) -> None:
        # We never want a mask to turn NULL into a literal — that would
        # fabricate data and break NULL-aware downstream joins.
        # Every mask that handles NULLs does so with a CASE branch.
        assert "WHEN ssn IS NULL THEN NULL" in sql
        assert "WHEN email IS NULL THEN NULL" in sql
        assert "WHEN phone IS NULL THEN NULL" in sql


# ---------------------------------------------------------------------------
# Audit columns — audit_columns.sql
# ---------------------------------------------------------------------------


class TestAuditColumns:

    @pytest.fixture(scope="class")
    def sql(self) -> str:
        return _normalise(_read_compiled("test_audit_output"))

    def test_adds_run_id(self, sql: str) -> None:
        # run_id is the pivot column for ops debugging — don't let it drop.
        assert ", 'test_run_123' as run_id" in sql

    def test_adds_processed_timestamp_as_function_call(self, sql: str) -> None:
        # Must be current_timestamp() — a literal would make every row identical.
        assert "current_timestamp() as processed_timestamp" in sql

    def test_adds_source_file(self, sql: str) -> None:
        assert ", 'test_file.csv' as source_file" in sql

    def test_does_not_drop_original_column(self, sql: str) -> None:
        # add_audit_columns should *append*, not replace.
        assert "'dummy' as col" in sql


# ---------------------------------------------------------------------------
# Enrichment — enrichment.sql
# ---------------------------------------------------------------------------


class TestEnrichmentRules:

    @pytest.fixture(scope="class")
    def sql(self) -> str:
        return _normalise(_read_compiled("test_enrichment_output"))

    def test_date_parts_extracts_year_month_day(self, sql: str) -> None:
        assert "EXTRACT(YEAR FROM application_date) as app_year" in sql
        assert "EXTRACT(MONTH FROM application_date) as app_month" in sql
        assert "EXTRACT(DAY FROM application_date) as app_day" in sql

    def test_date_parts_adds_day_name(self, sql: str) -> None:
        # FORMAT_DATE('%A', ...) is BQ-specific; locking it in guards against
        # someone swapping it for a non-portable function.
        assert "FORMAT_DATE('%A', application_date) as app_day_name" in sql

    def test_bucket_emits_case_with_all_branches(self, sql: str) -> None:
        # Our test model declared three buckets + an implicit 'Other' else.
        assert "WHEN loan_amount <100000 THEN 'Small'" in sql
        assert "WHEN loan_amount BETWEEN 100000 AND 500000 THEN 'Medium'" in sql
        assert "WHEN loan_amount >500000 THEN 'Large'" in sql
        assert "ELSE 'Other'" in sql
        assert "END as amount_category" in sql

    def test_lookup_emits_case_on_column(self, sql: str) -> None:
        # LOOKUP rule type should compile to `CASE <col> WHEN ...`.
        assert "CASE status" in sql
        assert "WHEN 'A' THEN 'Active'" in sql
        assert "WHEN 'I' THEN 'Inactive'" in sql
        assert "ELSE 'Unknown'" in sql
        assert "END as status_desc" in sql

    def test_expression_rule_passes_through_verbatim(self, sql: str) -> None:
        # The EXPRESSION rule type is an escape hatch — it should embed the
        # author's SQL as-is, not wrap or rewrite it.
        assert (
            'CASE WHEN credit_score >= 700 THEN "Good" ELSE "Bad" END '
            "as credit_quality"
        ) in sql


# ---------------------------------------------------------------------------
# Data quality — data_quality_check.sql
# ---------------------------------------------------------------------------


class TestDataQualityChecks:

    @pytest.fixture(scope="class")
    def sql(self) -> str:
        return _normalise(_read_compiled("test_dq_output"))

    def test_not_null_predicate_present(self, sql: str) -> None:
        # generic_not_null_and_unique must flag NULLs as failures.
        assert "WHERE ssn IS NULL" in sql

    def test_uniqueness_uses_count_distinct_vs_count(self, sql: str) -> None:
        # The uniqueness half of the check compares DISTINCT count to total.
        # If someone rewrites this to COUNT(ssn) vs COUNT(*), NULLs would
        # hide duplicates — this assertion prevents that regression.
        assert "COUNT(DISTINCT ssn)" in sql
        assert "< COUNT(*)" in sql


if __name__ == "__main__":  # pragma: no cover - manual invocation
    sys.exit(pytest.main([__file__, "-v"]))
