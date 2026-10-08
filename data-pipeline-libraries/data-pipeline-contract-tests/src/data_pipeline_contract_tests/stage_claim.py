"""StageClaim contract test mixin.

Java mirror: ``com.enrichmeai.culvert.contracttests.StageClaimContractTest``
(``data-pipeline-libraries-java/data-pipeline-contract-tests-java/src/main/java/com/enrichmeai/culvert/contracttests/StageClaimContractTest.java``),
test for test; each test names its Java twin.

**Deterministic, not statistical.** No test spawns threads and hopes for a race. Two claimants are
driven in a fixed order from one thread: A acquires and holds, then B tries the same key with a
bounded wait. B is guaranteed to wait, because A holds the claim for B's whole call, and B's outcome
is asserted exactly.

The wake-up cases (B is waiting, then A completes or abandons) need B on a second thread. They stay
deterministic because the ``await_waiting`` fixture reports, from the backend's own state, that B is
waiting before A moves.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from data_pipeline_core.stage_claim_api.models import Acquired, Completed, Held, StageKey

ZERO = timedelta(0)


def fresh_key() -> StageKey:
    return StageKey(f"unit-{uuid.uuid4()}", "load", "2026-10-01")


class StageClaimContract:
    """Mixin. Subclasses provide the fixtures:

    - ``stage_claim``: the :class:`StageClaim` under test. Every ``try_claim`` call must be an
      independent claimant (a separate session, connection or lock owner), even from the same
      thread: a backend whose lock is re-entrant per thread lets B acquire what A holds, and fails.
    - ``await_waiting``: a callable ``(key) -> None`` that returns once a claimant is waiting on
      ``key``, read from the backend's own state (a lock queue, the server's session list), never a
      sleep. The default fails, as Java's ``awaitWaiting`` does
      (``StageClaimContractTest.java:50``):
      a backend that cannot show a claimant waiting cannot prove the wake-up guarantees.
    """

    @pytest.fixture
    def await_waiting(self):
        pytest.fail(
            f"{type(self).__name__} must override the await_waiting fixture, so the wake-up cases "
            "are ordered by the backend's state rather than by a sleep"
        )

    @pytest.fixture(autouse=True)
    def _claims_end_with_the_test(self, stage_claim):
        """Close every claim a test acquired, also when its assertion failed partway.

        Otherwise a broken backend's stray claim stays held after its test, and the next test
        blocks on it instead of failing. Closing an ended claim does nothing (``Claim.close``).
        """
        acquired = []
        try_claim = stage_claim.try_claim

        def recording(key, claimant, max_wait):
            result = try_claim(key, claimant, max_wait)
            if isinstance(result, Acquired):
                acquired.append(result.claim)
            return result

        stage_claim.try_claim = recording
        yield
        stage_claim.try_claim = try_claim
        for claim in acquired:
            try:
                claim.close()
            except Exception:  # teardown only: the test has already reported what went wrong
                pass

    @pytest.fixture
    def held_wait(self) -> timedelta:
        """How long B waits for A in the held cases (``StageClaimContractTest.java:56``)."""
        return timedelta(milliseconds=300)

    @staticmethod
    def _acquire(stage_claim, key: StageKey, claimant: str):
        result = stage_claim.try_claim(key, claimant, ZERO)
        assert isinstance(result, Acquired), f"{claimant} should acquire {key}, got {result!r}"
        return result.claim

    # Java: aFreshStageIsAcquired
    def test_a_fresh_stage_is_acquired(self, stage_claim):
        key = fresh_key()
        with self._acquire(stage_claim, key, "A") as a:
            assert a.key == key
            assert a.claimant == "A"

    # Java: whileAHoldsBWaitsAndIsHeld
    def test_while_a_holds_b_waits_and_is_held(self, stage_claim, held_wait):
        key = fresh_key()
        with self._acquire(stage_claim, key, "A") as a:
            assert a.key == key
            start = time.monotonic()
            b = stage_claim.try_claim(key, "B", held_wait)
            waited = time.monotonic() - start

            assert b == Held(key)
            assert waited >= held_wait.total_seconds() / 2, \
                "B must block for its wait, not return at once"

    # Java: whileAHoldsAZeroWaitClaimIsHeldAtOnce
    def test_while_a_holds_a_zero_wait_claim_is_held_at_once(self, stage_claim):
        key = fresh_key()
        with self._acquire(stage_claim, key, "A") as a:
            assert a.claimant == "A"
            assert stage_claim.try_claim(key, "B", ZERO) == Held(key)

    # Java: afterACompletesBSeesCompletedAndNeverRunsTheStage
    def test_after_a_completes_b_sees_completed_and_never_runs_the_stage(
            self, stage_claim, held_wait):
        key = fresh_key()
        with self._acquire(stage_claim, key, "A") as a:
            assert isinstance(stage_claim.try_claim(key, "B", ZERO), Held)
            a.complete()
        b = stage_claim.try_claim(key, "B", held_wait)
        assert isinstance(b, Completed)
        assert b.key == key
        assert b.completed_by == "A"
        assert isinstance(stage_claim.try_claim(key, "A", ZERO), Completed), \
            "not even the claimant that completed it runs it again"

    # Java: aWaitingClaimantWakesToCompletedWhenTheHolderCompletes
    def test_a_waiting_claimant_wakes_to_completed_when_the_holder_completes(
            self, stage_claim, await_waiting):
        key = fresh_key()
        a = self._acquire(stage_claim, key, "A")
        with ThreadPoolExecutor(max_workers=1) as second:
            try:
                b = second.submit(stage_claim.try_claim, key, "B", timedelta(seconds=30))
                await_waiting(key)
                assert not b.done(), "B is still waiting on A"

                a.complete()

                result = b.result(timeout=10)
                assert isinstance(result, Completed)
                assert result.completed_by == "A"
            finally:
                a.close()

    # Java: aWaitingClaimantWakesToAcquiredWhenTheHolderAbandons
    def test_a_waiting_claimant_wakes_to_acquired_when_the_holder_abandons(
            self, stage_claim, await_waiting):
        key = fresh_key()
        a = self._acquire(stage_claim, key, "A")
        with ThreadPoolExecutor(max_workers=1) as second:
            b = second.submit(stage_claim.try_claim, key, "B", timedelta(seconds=30))
            try:
                await_waiting(key)
                assert not b.done()

                a.close()

                result = b.result(timeout=10)
                assert isinstance(result, Acquired)
                with result.claim as claim_b:
                    assert claim_b.claimant == "B"
            finally:
                a.close()
                if b.done() and b.exception() is None and isinstance(b.result(), Acquired):
                    b.result().claim.close()

    # Java: anAbandonedClaimIsAcquiredByTheNextClaimant
    def test_an_abandoned_claim_is_acquired_by_the_next_claimant(self, stage_claim):
        key = fresh_key()
        a = self._acquire(stage_claim, key, "A")
        a.close()  # abandoned: A stopped without completing

        with self._acquire(stage_claim, key, "B") as b:
            assert b.claimant == "B"
            b.complete()
        assert stage_claim.try_claim(key, "C", ZERO).completed_by == "B"

    # Java: differentKeysDoNotContend
    def test_different_keys_do_not_contend(self, stage_claim):
        key = fresh_key()
        unit_key = StageKey(key.unit + "-x", key.stage, key.period)
        stage_key = StageKey(key.unit, "transform", key.period)
        period_key = StageKey(key.unit, key.stage, "2026-10-02")
        with self._acquire(stage_claim, key, "A") as a, \
                self._acquire(stage_claim, unit_key, "B") as other_unit, \
                self._acquire(stage_claim, stage_key, "C") as other_stage, \
                self._acquire(stage_claim, period_key, "D") as other_period:
            assert other_unit.key != a.key
            assert other_stage.key != a.key
            assert other_period.key != a.key

    # Java: aClaimEndsExactlyOnce
    def test_a_claim_ends_exactly_once(self, stage_claim):
        a = self._acquire(stage_claim, fresh_key(), "A")
        a.complete()
        with pytest.raises(RuntimeError):
            a.complete()
        a.close()  # closing after completing is a no-op

        b = self._acquire(stage_claim, fresh_key(), "B")
        b.close()
        b.close()  # idempotent
        with pytest.raises(RuntimeError):
            b.complete()

    # Java: completionIsEmptyUntilTheStageCompletesAndThenNamesTheHolder
    def test_completion_is_empty_until_the_stage_completes_and_then_names_the_holder(
            self, stage_claim):
        key = fresh_key()
        assert stage_claim.completion(key) is None, "never claimed"

        with self._acquire(stage_claim, key, "A") as a:
            assert stage_claim.completion(key) is None, "held, not completed"
            a.complete()
        done = stage_claim.completion(key)
        assert done is not None
        assert done.key == key
        assert done.completed_by == "A"
        assert stage_claim.try_claim(key, "B", ZERO) == done, \
            "the read and a claim agree on the completion"

    # Java: anAbandonedStageReadsAsNotCompleted
    def test_an_abandoned_stage_reads_as_not_completed(self, stage_claim):
        key = fresh_key()
        self._acquire(stage_claim, key, "A").close()
        assert stage_claim.completion(key) is None

    # Java: readingACompletionNeverClaimsTheStage
    def test_reading_a_completion_never_claims_the_stage(self, stage_claim):
        key = fresh_key()
        with self._acquire(stage_claim, key, "A") as a:
            assert stage_claim.completion(key) is None
            assert a.claimant == "A"
            assert stage_claim.try_claim(key, "B", ZERO) == Held(key), \
                "A still holds the stage after the read"
        assert stage_claim.completion(key) is None
        with self._acquire(stage_claim, key, "B") as b:
            assert b.claimant == "B", "the read left nothing held"

    # Java: badArgumentsAreRejected
    def test_bad_arguments_are_rejected(self, stage_claim):
        key = fresh_key()
        with pytest.raises(TypeError):
            stage_claim.try_claim(None, "A", ZERO)
        with pytest.raises(ValueError):
            stage_claim.try_claim(key, " ", ZERO)
        with pytest.raises(ValueError):
            stage_claim.try_claim(key, "A", timedelta(milliseconds=-1))
        with pytest.raises(TypeError):
            stage_claim.completion(None)
        with pytest.raises(ValueError):
            StageKey("u", "", "p")
