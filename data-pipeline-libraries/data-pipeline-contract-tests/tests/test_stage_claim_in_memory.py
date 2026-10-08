"""The reference: an in-memory StageClaim that passes StageClaimContract, so a failure in a backend's
run of the suite is the backend's, not the suite's.

Java mirror: ``InMemoryStageClaimContractTest.java`` (data-pipeline-contract-tests-java/src/test).
Java uses a ``Semaphore`` per key so that a second claim from the same thread contends like a second
session; this uses a condition and a holder flag per key for the same reason (it is not re-entrant),
and counts waiters so ``await_waiting`` can read them.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pytest

from data_pipeline_contract_tests import StageClaimContract
from data_pipeline_core.stage_claim_api.models import Acquired, Completed, Held, StageKey


class _Slot:
    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.held = False
        self.waiters = 0


class InMemoryStageClaim:
    def __init__(self) -> None:
        self._slots: Dict[StageKey, _Slot] = {}
        self._done: Dict[StageKey, Completed] = {}
        self._lock = threading.Lock()

    def _slot(self, key: StageKey) -> _Slot:
        with self._lock:
            return self._slots.setdefault(key, _Slot())

    def has_waiter(self, key: StageKey) -> bool:
        slot = self._slots.get(key)
        return slot is not None and slot.waiters > 0

    def completion(self, key: StageKey) -> Optional[Completed]:
        if key is None:
            raise TypeError("key must not be None")
        return self._done.get(key)

    def try_claim(self, key: StageKey, claimant: str, max_wait: timedelta):
        if key is None or claimant is None or max_wait is None:
            raise TypeError("key, claimant and max_wait must not be None")
        if not claimant.strip():
            raise ValueError("claimant must not be blank")
        if max_wait < timedelta(0):
            raise ValueError("max_wait must not be negative")
        slot = self._slot(key)
        deadline = time.monotonic() + max_wait.total_seconds()
        with slot.cond:
            slot.waiters += 1
            try:
                while slot.held:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        done = self._done.get(key)
                        return done if done is not None else Held(key)
                    slot.cond.wait(left)
            finally:
                slot.waiters -= 1
            done = self._done.get(key)
            if done is not None:
                return done
            slot.held = True
        return Acquired(_InMemoryClaim(self, slot, key, claimant))


class _InMemoryClaim:
    def __init__(self, owner: InMemoryStageClaim, slot: _Slot, key: StageKey, claimant: str) -> None:
        self._owner, self._slot, self._key, self._claimant = owner, slot, key, claimant
        self._ended = False
        self._lock = threading.Lock()

    @property
    def key(self) -> StageKey:
        return self._key

    @property
    def claimant(self) -> str:
        return self._claimant

    def _release(self) -> None:
        with self._slot.cond:
            self._slot.held = False
            self._slot.cond.notify_all()

    def complete(self) -> None:
        with self._lock:
            if self._ended:
                raise RuntimeError(f"claim on {self._key} already ended")
            self._owner._done[self._key] = Completed(self._key, self._claimant, datetime.now(timezone.utc))
            self._ended = True
            self._release()

    def close(self) -> None:
        with self._lock:
            if not self._ended:
                self._ended = True
                self._release()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class TestInMemoryStageClaim(StageClaimContract):

    @pytest.fixture
    def stage_claim(self):
        return InMemoryStageClaim()

    @pytest.fixture
    def await_waiting(self, stage_claim):
        def wait(key: StageKey) -> None:
            deadline = time.monotonic() + 10
            while not stage_claim.has_waiter(key):
                if time.monotonic() > deadline:
                    raise AssertionError(f"no claimant started waiting on {key}")
                time.sleep(0.001)
        return wait


class TestTheDefaultAwaitWaitingFails(StageClaimContract):
    """A backend cannot skip proving the wake-up cases: the default await_waiting fails
    (Java: ``StageClaimContractTest.java:50``)."""

    @pytest.fixture
    def stage_claim(self):
        return InMemoryStageClaim()

    def test_the_default_await_waiting_fails(self, request):
        with pytest.raises(pytest.fail.Exception, match="must override the await_waiting fixture"):
            request.getfixturevalue("await_waiting")


# Collect the contract once, through TestInMemoryStageClaim, not again through this class.
for _name in [n for n in dir(StageClaimContract) if n.startswith("test_")]:
    setattr(TestTheDefaultAwaitWaitingFails, _name, None)
