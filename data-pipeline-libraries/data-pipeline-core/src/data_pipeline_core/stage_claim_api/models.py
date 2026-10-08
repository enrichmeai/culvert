"""What a stage claim claims, and what a claim attempt returns.

Each type mirrors its Java twin; the citations are to
``data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/stageclaim/``.
Java's ``NullPointerException`` is ``TypeError`` here, ``IllegalArgumentException`` is
``ValueError`` and ``IllegalStateException`` is ``RuntimeError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Union, runtime_checkable


def _require_text(value: object, name: str) -> None:
    if value is None:
        raise TypeError(f"{name} must not be None")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


@dataclass(frozen=True)
class StageKey:
    """One stage of one unit for one period. Mirrors ``StageKey.java:13``.

    The unit is the isolation key (a source, an entity, a tenant: whatever a fan-out runs in
    parallel), the stage names a step of the pipeline, and the period is the slice of time the run
    covers, such as ``2026-10-01``. All three are opaque, non-blank strings; the backend compares
    them exactly.
    """

    unit: str
    stage: str
    period: str

    def __post_init__(self) -> None:
        _require_text(self.unit, "unit")
        _require_text(self.stage, "stage")
        _require_text(self.period, "period")

    def __str__(self) -> str:  # StageKey.java:29
        return f"{self.unit}/{self.stage}/{self.period}"


@runtime_checkable
class Claim(Protocol):
    """A held claim on a stage. Mirrors ``Claim.java:11``.

    The holder ends it exactly once: :meth:`complete` records the stage as done, :meth:`close`
    abandons it. Use it as a context manager so an exception abandons it rather than leaking it.
    """

    @property
    def key(self) -> StageKey:  # Claim.java:14
        """The stage this claim holds."""
        ...

    @property
    def claimant(self) -> str:  # Claim.java:17
        """Who holds it, as given to ``try_claim``."""
        ...

    def complete(self) -> None:  # Claim.java:26
        """Record the stage as done and release the claim.

        :raises RuntimeError: if the claim was already completed or closed, or if the backend could
            not record the completion (for example, its session died). In both cases the stage is
            not recorded as done by this call.
        """
        ...

    def close(self) -> None:  # Claim.java:30
        """Release the claim. If it was not completed, the stage stays not done. Idempotent."""
        ...

    def __enter__(self) -> "Claim":
        ...

    def __exit__(self, *exc: object) -> None:
        ...


@dataclass(frozen=True)
class Acquired:
    """The caller now holds the stage; it must complete or close the claim.

    Mirrors ``ClaimResult.Acquired`` (``ClaimResult.java:14``).
    """

    claim: Claim

    def __post_init__(self) -> None:
        if self.claim is None:
            raise TypeError("claim must not be None")

    @property
    def key(self) -> StageKey:
        return self.claim.key


@dataclass(frozen=True)
class Held:
    """Another claimant held the stage for the whole wait. The stage is not done yet.

    Mirrors ``ClaimResult.Held`` (``ClaimResult.java:26``).
    """

    key: StageKey

    def __post_init__(self) -> None:
        if self.key is None:
            raise TypeError("key must not be None")


@dataclass(frozen=True)
class Completed:
    """The stage is already done. It is never run again under this key.

    Mirrors ``ClaimResult.Completed`` (``ClaimResult.java:33``). ``completed_at`` should be a
    timezone-aware datetime (Java's ``Instant``); ``PostgresStageClaim`` returns it in UTC. This
    type does not check it.
    """

    key: StageKey
    completed_by: str
    completed_at: datetime

    def __post_init__(self) -> None:
        for name in ("key", "completed_by", "completed_at"):
            if getattr(self, name) is None:
                raise TypeError(f"{name} must not be None")


# The sealed ``ClaimResult`` interface (``ClaimResult.java:7``): exactly one of the three.
ClaimResult = Union[Acquired, Held, Completed]


class CompletionChecker:
    """A :class:`StageClaim` as the checker a rendered DAG's stage gate calls.

    The Airflow and Composer renderers (Java ``StageGateConfig``) emit
    ``_stage_gate.completion(unit=..., stage=..., period=...)`` and treat ``None`` as "not
    completed". This adapts any ``StageClaim`` to that call, so ``StageGateConfig.builder(
    "CompletionChecker(PostgresStageClaim())")`` gates on the real store.
    """

    def __init__(self, stage_claim: object) -> None:
        if stage_claim is None:
            raise TypeError("stage_claim must not be None")
        self._stage_claim = stage_claim

    def completion(self, *, unit: str, stage: str, period: str) -> "Completed | None":
        return self._stage_claim.completion(StageKey(unit, stage, period))
