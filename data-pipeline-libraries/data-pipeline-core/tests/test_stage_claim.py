"""StageClaim's value types and Protocol (#196).

Java mirrors: StageKey.java, ClaimResult.java, Claim.java and contracts/StageClaim.java in
data-pipeline-libraries-java/data-pipeline-core-java.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from data_pipeline_core import (
    Acquired,
    Claim,
    Completed,
    Held,
    StageClaim,
    StageKey,
)
from data_pipeline_core.autoconfig import AutoConfig, register_adapter, reset_process_registry


# ---------------------------------------------------------------- StageKey

def test_a_key_is_three_exact_strings_and_reads_as_unit_stage_period():
    key = StageKey("orders", "load", "2026-10-01")
    assert (key.unit, key.stage, key.period) == ("orders", "load", "2026-10-01")
    assert str(key) == "orders/load/2026-10-01"
    assert key == StageKey("orders", "load", "2026-10-01")
    assert key != StageKey("Orders", "load", "2026-10-01"), "compared exactly"
    assert hash(key) == hash(StageKey("orders", "load", "2026-10-01"))


@pytest.mark.parametrize("field", ["unit", "stage", "period"])
def test_a_blank_part_is_refused_naming_it(field):
    parts = {"unit": "orders", "stage": "load", "period": "2026-10-01", field: "  "}
    with pytest.raises(ValueError, match=field):
        StageKey(**parts)


@pytest.mark.parametrize("bad", [None, 7])
def test_a_missing_or_non_text_part_is_a_type_error(bad):
    with pytest.raises(TypeError, match="unit"):
        StageKey(bad, "load", "2026-10-01")


def test_a_key_is_immutable():
    key = StageKey("orders", "load", "2026-10-01")
    with pytest.raises(AttributeError):
        key.unit = "customers"


# ---------------------------------------------------------------- results

class _Claim:
    def __init__(self, key: StageKey) -> None:
        self._key = key

    @property
    def key(self) -> StageKey:
        return self._key

    @property
    def claimant(self) -> str:
        return "A"

    def complete(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def test_the_three_results_carry_their_key():
    key = StageKey("orders", "load", "2026-10-01")
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert Acquired(_Claim(key)).key == key
    assert Held(key).key == key
    assert Completed(key, "worker-1", at).key == key
    assert Held(key) == Held(key)
    assert Completed(key, "worker-1", at) == Completed(key, "worker-1", at)


@pytest.mark.parametrize("make", [
    lambda key, at: Acquired(None),
    lambda key, at: Held(None),
    lambda key, at: Completed(None, "w", at),
    lambda key, at: Completed(key, None, at),
    lambda key, at: Completed(key, "w", None),
])
def test_a_result_refuses_none(make):
    with pytest.raises(TypeError):
        make(StageKey("orders", "load", "2026-10-01"), datetime.now(timezone.utc))


# ---------------------------------------------------------------- the Protocol

class _StructuralStageClaim:
    def try_claim(self, key: StageKey, claimant: str, max_wait: timedelta):
        return Held(key)

    def completion(self, key: StageKey) -> Optional[Completed]:
        return None


def test_the_protocols_are_runtime_checkable():
    assert isinstance(_StructuralStageClaim(), StageClaim)
    assert not isinstance(object(), StageClaim)
    assert isinstance(_Claim(StageKey("u", "s", "p")), Claim)


def test_autoconfig_has_a_stage_claim_slot():
    reset_process_registry()
    try:
        register_adapter("stage_claim")(_StructuralStageClaim)
        assert AutoConfig().stage_claim == []
        from data_pipeline_core.autoconfig import discover
        assert _StructuralStageClaim in discover().all("stage_claim")
    finally:
        reset_process_registry()


def test_completion_checker_adapts_a_stage_claim_to_the_rendered_gate_call():
    from data_pipeline_core.stage_claim_api import CompletionChecker
    key = StageKey("orders", "load", "2026-10-01")
    done = Completed(key, "worker-1", datetime(2026, 10, 1, tzinfo=timezone.utc))

    class _Store:
        def completion(self, k):
            return done if k == key else None

    checker = CompletionChecker(_Store())
    assert checker.completion(unit="orders", stage="load", period="2026-10-01") == done
    assert checker.completion(unit="orders", stage="publish", period="2026-10-01") is None
    with pytest.raises(TypeError):
        CompletionChecker(None)
