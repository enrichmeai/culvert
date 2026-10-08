"""StageClaim — an atomic claim on one stage of one unit for one period.

Python mirror of the Java ``StageClaim`` port
(``data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/StageClaim.java:34``),
method for method. Control-plane epic #188; this mirror is #196.

**A stage cannot double-start, and an interrupted stage is picked up again by the next claimant.**

- At most one claimant holds a key at a time.
- Once a holder calls :meth:`Claim.complete`, every later claim on the key returns
  :class:`Completed`: the stage never runs twice.
- If the holder abandons the claim (:meth:`Claim.close` without completing) or dies, the stage is
  not done and the next claimant acquires it.

It is an optional capability: only a backend that can lock implements it (today: PostgreSQL, in
``data-pipeline-postgres``). It is a separate port from ``JobControlRepository`` because a claim is
keyed by :class:`StageKey`, not a run id, and because two of the job-control backends cannot hold a
lock. How a dead holder's claim is released is the backend's to state.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional, Protocol, runtime_checkable

from data_pipeline_core.stage_claim_api.models import ClaimResult, Completed, StageKey


@runtime_checkable
class StageClaim(Protocol):
    """Claim a stage before running it; read whether it is done without claiming it."""

    def try_claim(self, key: StageKey, claimant: str, max_wait: timedelta) -> ClaimResult:
        """Try to claim ``key`` for ``claimant``, waiting up to ``max_wait`` for a current holder.

        Mirrors ``StageClaim.tryClaim`` (``StageClaim.java:46``). ``timedelta(0)`` does not wait.
        If the holder completes while this call waits, the result is :class:`Completed`; if it
        abandons, :class:`Acquired`; if it still holds when ``max_wait`` runs out, :class:`Held`.

        Every call is an independent claimant, even from the same thread: a second call on a held
        key is held, never re-entered.

        :raises TypeError: if an argument is None or of the wrong type
        :raises ValueError: if ``claimant`` is blank or ``max_wait`` is negative
        """
        ...

    def completion(self, key: StageKey) -> Optional[Completed]:
        """Read whether ``key`` has been completed.

        It does not claim the stage, wait, or block a claimant.

        Mirrors ``StageClaim.completion`` (``StageClaim.java:56``). None means not completed:
        never claimed, held right now, or abandoned. This is the read a gate re-check uses, so a
        check never makes a real claimant see :class:`Held`. A completion is final.

        :raises TypeError: if ``key`` is None
        """
        ...
