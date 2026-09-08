"""Python half of the cross-language conformance suite (docs/CONTRACT.md 10.6).

Reads the SAME fixtures as the Java suite
(data-pipeline-libraries-java/.../AuditEventConformanceTest.java). That shared
file - not a mirrored assertion in each language - is what stops the two
emitters drifting on column names, event kinds, or payload keys.

A MISSING FIXTURE FILE FAILS THIS SUITE. It must never skip. The external
review flagged a sibling project whose parity test pointed at a directory
deleted months earlier: it skipped silently while CI stayed green, so the guard
reported success while checking nothing. A guard that cannot fail is worse than
no guard, because it is believed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_pipeline_core.audit.events import CONTRACT_VERSION, AuditEvent, EventKind


def _fixtures_path() -> Path:
    """Walk up to the repo root rather than assuming a fixed depth."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "tests" / "contract" / "fixtures" / "audit_events.json"
        if candidate.exists():
            return candidate
    raise AssertionError(
        "Conformance fixtures not found: tests/contract/fixtures/audit_events.json. "
        "This is a FAILURE, never a skip - docs/CONTRACT.md 10.6 promises a shipped "
        "conformance suite, and a guard that quietly disables itself reports green "
        "while checking nothing."
    )


@pytest.fixture(scope="module")
def fixtures() -> dict:
    return json.loads(_fixtures_path().read_text())


def test_every_contract_event_kind_exists_in_python(fixtures):
    declared = list(fixtures["run_level_kinds"]) + list(fixtures["aggregate_kinds"])
    assert len(declared) == 7, "fixtures must enumerate all 7 kinds from section 4"
    for wire in declared:
        assert EventKind.from_wire(wire) is not None
    assert len(list(EventKind)) == len(declared)


def test_run_level_classification_matches_the_fixtures(fixtures):
    for wire in fixtures["run_level_kinds"]:
        assert EventKind.from_wire(wire).is_run_level() is True, (
            f"{wire} is run-level: a failed append must fail the pipeline"
        )
    for wire in fixtures["aggregate_kinds"]:
        assert EventKind.from_wire(wire).is_run_level() is False, (
            f"{wire} is an aggregate: a failed append dead-letters, never halts ingestion"
        )


def test_required_payload_keys_match_the_fixtures(fixtures):
    for wire, expected in fixtures["required_payload_keys"].items():
        kind = EventKind.from_wire(wire)
        assert sorted(kind.required_payload_keys) == sorted(expected), (
            f"{wire} payload keys must match the shared fixtures exactly"
        )


def test_contract_version_matches_the_fixtures(fixtures):
    assert CONTRACT_VERSION == fixtures["contract_version"]


def test_a_missing_required_payload_key_is_rejected_at_construction():
    # Fail here, loudly, rather than reading back as NULL from a JSON path.
    with pytest.raises(ValueError, match="quarantine_uri"):
        AuditEvent(
            "run-1", "Generic", "customers", EventKind.RECORD_REJECTED,
            datetime.now(timezone.utc), {"count": 2},
        )


def test_every_fixture_case_constructs_and_round_trips(fixtures):
    cases = fixtures["cases"]
    assert len(cases) == 7, "fixtures must exercise every kind"

    for case in cases:
        row = case["row"]
        kind = EventKind.from_wire(row["event_kind"])
        event = AuditEvent(
            run_id=row["run_id"],
            system_id=row["system_id"],
            entity=row["entity"],
            event_kind=kind,
            event_ts=datetime.now(timezone.utc),
            payload=row["payload"],
            producer=row.get("producer"),
            environment=row.get("environment"),
        )
        assert event.contract_version == row["contract_version"]
        assert event.failure_is_fatal() is case["run_level"], (
            f"{case['name']}: run-level classification must match the fixture"
        )
        for key in kind.required_payload_keys:
            assert key in event.payload


def test_fixture_rows_carry_every_required_column(fixtures):
    required = fixtures["required_columns"]
    for case in fixtures["cases"]:
        missing = [c for c in required if c not in case["row"]]
        assert not missing, f"{case['name']} is missing required column(s) {missing}"


def test_an_unknown_event_kind_is_rejected_and_names_the_valid_ones():
    with pytest.raises(ValueError, match="RUN_START"):
        EventKind.from_wire("STAGE_COMPLETED")
