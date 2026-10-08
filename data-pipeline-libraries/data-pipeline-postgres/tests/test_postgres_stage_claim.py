"""PostgresStageClaim (Python) against a real PostgreSQL.

The shared StageClaimContract runs first (Java: ``PostgresStageClaimContractTest.java``), then the
PostgreSQL-specific cases of ``PostgresStageClaimTest.java``.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import psycopg2
import psycopg2.errors
import pytest

from conftest import await_lock_wait, query
from data_pipeline_contract_tests import StageClaimContract
from data_pipeline_core import Acquired, Completed, Held, StageClaim, StageKey
from data_pipeline_core.autoconfig import discover
from data_pipeline_postgres import PostgresStageClaim, connect_from_environment

ZERO = timedelta(0)


def tagged(dsn: str, application_name: str):
    return lambda: psycopg2.connect(dsn, application_name=application_name)


def fresh_key() -> StageKey:
    return StageKey(f"unit-{uuid.uuid4()}", "load", "2026-10-01")


class TestPostgresStageClaimContract(StageClaimContract):
    """Every session carries a per-test application name, which is how await_waiting finds B waiting
    on the lock in pg_stat_activity without mistaking another session for it."""

    @pytest.fixture
    def application_name(self):
        return f"stageclaim-contract-{uuid.uuid4()}"

    @pytest.fixture
    def stage_claim(self, dsn, application_name):
        return PostgresStageClaim(tagged(dsn, application_name))

    @pytest.fixture
    def await_waiting(self, dsn, application_name):
        return lambda key: await_lock_wait(dsn, application_name)


# ---------------------------------------------------------------- PostgresStageClaimTest.java

def test_it_is_a_stage_claim(dsn):
    assert isinstance(PostgresStageClaim(tagged(dsn, "x")), StageClaim)


def test_a_claimant_whose_session_dies_releases_the_stage(dsn):
    """Java: aClaimantWhoseSessionDiesReleasesTheStage (PostgresStageClaimTest.java:53)."""
    key = fresh_key()
    name = f"dead-claimant-{uuid.uuid4()}"
    claims = PostgresStageClaim(tagged(dsn, "survivor"))
    a = PostgresStageClaim(tagged(dsn, name)).try_claim(key, "A", ZERO).claim
    assert isinstance(claims.try_claim(key, "B", ZERO), Held)

    # Kill exactly A's session, the way a crashed worker's would end: the server rolls it back.
    rows = query(dsn, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = %s",
                 (name,))
    assert rows == [(True,)], "exactly A's session was ended"

    b = claims.try_claim(key, "B", timedelta(seconds=10))
    assert isinstance(b, Acquired), "the dead claimant's stage is free and not done"
    b.claim.close()

    with pytest.raises(RuntimeError):
        a.complete()  # a dead claim cannot record completion
    a.close()  # abandoning a dead claim does not raise


def test_a_completion_is_seen_by_every_later_instance(dsn):
    """Java: aCompletionIsSeenByEveryLaterInstance."""
    key = fresh_key()
    with PostgresStageClaim(tagged(dsn, "a")).try_claim(key, "A", ZERO).claim as a:
        a.complete()
    again = PostgresStageClaim(tagged(dsn, "b")).try_claim(key, "B", ZERO)
    assert isinstance(again, Completed)
    assert again.completed_at.tzinfo is not None


def test_the_stage_cannot_be_completed_twice_at_the_database(dsn):
    """Java: theStageCannotBeCompletedTwiceAtTheDatabase: the primary key, not just the code."""
    key = fresh_key()
    with PostgresStageClaim(tagged(dsn, "a")).try_claim(key, "A", ZERO).claim as a:
        a.complete()
    with pytest.raises(psycopg2.errors.UniqueViolation):
        query(dsn, "INSERT INTO job_control.stage_completions (unit, stage, period, completed_by, completed_at) "
                   "VALUES (%s, 'load', '2026-10-01', 'X', now())", (key.unit,))


def test_a_completion_written_by_the_java_claim_is_read_as_completed(dsn):
    """The same tables as Java: a row in Java's shape (PostgresStageClaim.java:346-349) is a completion."""
    key = fresh_key()
    query(dsn, "INSERT INTO job_control.stage_completions (unit, stage, period, completed_by, completed_at) "
               "VALUES (%s, %s, %s, 'java-worker', clock_timestamp())", (key.unit, key.stage, key.period))
    done = PostgresStageClaim(tagged(dsn, "py")).completion(key)
    assert done is not None and done.completed_by == "java-worker"


def test_schema_names_are_validated(dsn):
    """Java: schemaNamesAreValidated."""
    for bad in ("a.b", "x; drop", ""):
        with pytest.raises(ValueError):
            PostgresStageClaim(tagged(dsn, "x"), schema=bad)


def test_autoconfig_discovers_it_from_the_entry_point(dsn, monkeypatch):
    """Java: autoConfigDiscoversItFromTheServiceRegistration. Python's AutoConfig registers the class;
    the caller builds it, here from the CULVERT_POSTGRES_* settings."""
    params = dict(p.split("=", 1) for p in dsn.split())
    monkeypatch.setenv("CULVERT_POSTGRES_URL",
                       f"jdbc:postgresql://{params['host']}:{params['port']}/{params['dbname']}")
    monkeypatch.setenv("CULVERT_POSTGRES_USER", params["user"])
    found = discover().all("stage_claim")
    assert PostgresStageClaim in found
    claims = found[found.index(PostgresStageClaim)]()
    result = claims.try_claim(fresh_key(), "A", ZERO)
    assert isinstance(result, Acquired)
    result.claim.close()


def test_the_default_constructor_needs_a_url(monkeypatch):
    """Java: theServiceLoaderConstructorNeedsAUrl."""
    monkeypatch.delenv("CULVERT_POSTGRES_URL", raising=False)
    with pytest.raises(RuntimeError, match="CULVERT_POSTGRES_URL"):
        PostgresStageClaim()
    with pytest.raises(RuntimeError, match="CULVERT_POSTGRES_URL"):
        connect_from_environment()


def test_a_failed_connection_is_reported_not_swallowed():
    def refuse():
        raise psycopg2.OperationalError("connection refused")
    claims = PostgresStageClaim(refuse)
    with pytest.raises(RuntimeError, match="try_claim failed: connection refused"):
        claims.try_claim(fresh_key(), "A", ZERO)
    with pytest.raises(RuntimeError, match="completion failed: connection refused"):
        claims.completion(fresh_key())


def test_a_claimant_that_is_not_a_string_is_a_type_error(dsn):
    with pytest.raises(TypeError):
        PostgresStageClaim(tagged(dsn, "x")).try_claim(StageKey("u", "s", "p"), 5, timedelta(0))
