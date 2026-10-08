"""StageClaim on PostgreSQL: the claim is a row lock held by an open transaction.

Python side of the Java ``PostgresStageClaim``
(``data-pipeline-libraries-java/data-pipeline-postgres-java/src/main/java/com/enrichmeai/culvert/postgres/PostgresStageClaim.java``,
cited below as ``PostgresStageClaim.java:<line>``). It runs the same statements against the same
tables, so Java and Python claimants contend for the same stages.

How a claim works (``PostgresStageClaim.java:24-38``):

1. Make sure the key's row exists in ``stage_claims`` (an autocommitted
   ``INSERT ... ON CONFLICT DO NOTHING``).
2. Open a READ COMMITTED transaction and lock that row with ``SELECT ... FOR UPDATE``, waiting at
   most ``max_wait`` (``lock_timeout``, or ``NOWAIT`` for zero). If the wait runs out
   (SQLSTATE 55P03), the result is :class:`Held`.
3. With the lock held, look the key up in ``stage_completions``. A row there means the stage is
   done: :class:`Completed`. READ COMMITTED means this read sees a completion that the previous
   holder committed while we waited.
4. Otherwise :class:`Acquired`: the transaction, and so the lock, stay open until
   :meth:`Claim.complete` inserts the completion row and commits, or :meth:`Claim.close` rolls back.

The lock lives exactly as long as the claimant's transaction (decided in #195): if the claimant
dies, its session ends and the server releases the lock. What that leaves to the deployment: set
``idle_in_transaction_session_timeout`` and TCP keepalives so the server ends a hung holder's
session; size connections for the stages that run at once (a claim holds one for the whole
stage); make every stage safe to re-run from its start.

The tables come from the ``job_control.sql`` that the Java ``data-pipeline-postgres`` ships; apply
it once per database.
"""

from __future__ import annotations

import os
import re
import threading
from datetime import timedelta, timezone
from typing import Any, Callable, Optional

import psycopg2
import psycopg2.errors
import psycopg2.extensions

from data_pipeline_core.stage_claim_api.models import Acquired, Completed, Held, StageKey

DEFAULT_SCHEMA = "job_control"  # PostgresStageClaim.java:65
LOCK_NOT_AVAILABLE = "55P03"  # PostgresStageClaim.java:67
# lock_timeout is an int of milliseconds (PostgresStageClaim.java:199-201)
_MAX_LOCK_TIMEOUT_MS = 2**31 - 1
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")  # PostgresJobControlRepository.java:78-79

Connect = Callable[[], Any]


def connect_from_environment() -> Connect:
    """A connection factory from ``CULVERT_POSTGRES_URL``, ``_USER`` and ``_PASSWORD``.

    The environment variables the Java adapters read (``PostgresStageClaim.java:98-110``); the
    ``culvert.postgres.*`` system properties Java falls back to have no Python twin. The URL may be
    the Java ``jdbc:postgresql://host:port/db`` form, which is read as the libpq URI
    ``postgresql://host:port/db``, or any libpq connection string. JDBC-only URL parameters (such
    as ``ApplicationName``) are not libpq's and are refused by the server's client library.

    :raises RuntimeError: if ``CULVERT_POSTGRES_URL`` is not set
    """
    url = os.environ.get("CULVERT_POSTGRES_URL", "").strip()
    if not url:
        raise RuntimeError(
            "PostgresStageClaim needs CULVERT_POSTGRES_URL, a jdbc:postgresql:// URL or a libpq "
            "connection string")
    if url.startswith("jdbc:"):
        url = url[len("jdbc:"):]
    extra = {}
    for env, arg in (("CULVERT_POSTGRES_USER", "user"), ("CULVERT_POSTGRES_PASSWORD", "password")):
        value = os.environ.get(env, "")
        if value.strip():  # like Java's isBlank check; the value itself is passed as set
            extra[arg] = value
    return lambda: psycopg2.connect(url, **extra)


def _check_claim_args(key, claimant, max_wait) -> None:
    _check_key(key)
    if claimant is None or max_wait is None:
        raise TypeError("claimant and max_wait must not be None")
    if not isinstance(max_wait, timedelta):
        raise TypeError(f"max_wait must be a timedelta, got {type(max_wait).__name__}")
    if not isinstance(claimant, str):
        raise TypeError(f"claimant must be a str, got {type(claimant).__name__}")
    if not claimant.strip():
        raise ValueError("claimant must not be blank")
    if max_wait < timedelta(0):
        raise ValueError(f"max_wait must not be negative, got {max_wait}")


def _check_key(key: object) -> None:
    if key is None:
        raise TypeError("key must not be None")
    if not isinstance(key, StageKey):
        raise TypeError(f"key must be a StageKey, got {type(key).__name__}")


class PostgresStageClaim:
    """:class:`~data_pipeline_core.contracts.stage_claim.StageClaim` on PostgreSQL.

    :param connect: returns a new DB-API connection to the database; every ``try_claim`` takes its
        own connection, so every call is an independent claimant. Default:
        :func:`connect_from_environment`.
    :param schema: the schema holding ``stage_claims`` and ``stage_completions``
    """

    def __init__(self, connect: Optional[Connect] = None, schema: str = DEFAULT_SCHEMA) -> None:
        if schema is None:
            raise TypeError("schema must not be None")
        if not _NAME.fullmatch(schema):  # PostgresStageClaim.java:83-85
            raise ValueError(f"schema must be a single plain name: {schema}")
        self._connect = connect if connect is not None else connect_from_environment()
        self._claims = f'"{schema}"."stage_claims"'
        self._completions = f'"{schema}"."stage_completions"'

    # PostgresStageClaim.java:122
    def try_claim(self, key: StageKey, claimant: str, max_wait: timedelta):
        _check_claim_args(key, claimant, max_wait)
        try:
            conn = self._connect()
        except psycopg2.Error as e:
            raise RuntimeError(f"PostgreSQL try_claim failed: {e}") from e
        try:
            conn.autocommit = True
            self._ensure_row(conn, key)
            conn.autocommit = False
            conn.set_session(isolation_level=psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
            if not self._lock(conn, key, max_wait):
                conn.rollback()
                conn.close()
                return Held(key)
            done = self._completion(conn, key)
            if done is not None:
                conn.rollback()
                conn.close()
                return done
            return Acquired(_PostgresClaim(conn, self._completions, key, claimant))
        except BaseException as e:
            _abort(conn)
            if isinstance(e, psycopg2.Error):
                raise RuntimeError(f"PostgreSQL try_claim failed: {e}") from e
            raise

    # PostgresStageClaim.java:166
    def completion(self, key: StageKey) -> Optional[Completed]:
        """A single autocommit read of ``stage_completions``: it takes no lock and waits on none."""
        _check_key(key)
        try:
            conn = self._connect()
        except psycopg2.Error as e:
            raise RuntimeError(f"PostgreSQL completion failed: {e}") from e
        try:
            conn.autocommit = True
            return self._completion(conn, key)
        except psycopg2.Error as e:
            raise RuntimeError(f"PostgreSQL completion failed: {e}") from e
        finally:
            conn.close()

    # PostgresStageClaim.java:184
    def _ensure_row(self, conn: Any, key: StageKey) -> None:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self._claims} (unit, stage, period) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (key.unit, key.stage, key.period),
            )

    # PostgresStageClaim.java:193
    def _lock(self, conn: Any, key: StageKey, max_wait: timedelta) -> bool:
        """True if the lock was taken within ``max_wait``; False if another session held it."""
        select = (f"SELECT 1 FROM {self._claims} WHERE unit = %s AND stage = %s AND period = %s "
                  "FOR UPDATE")
        timed = max_wait > timedelta(0)
        with conn.cursor() as cur:
            if not timed:
                select += " NOWAIT"
            else:
                ms = min(_MAX_LOCK_TIMEOUT_MS, max(1, max_wait // timedelta(milliseconds=1)))
                cur.execute(f"SET LOCAL lock_timeout = '{ms}ms'")
            try:
                cur.execute(select, (key.unit, key.stage, key.period))
            except psycopg2.Error as e:
                if e.pgcode == LOCK_NOT_AVAILABLE:
                    return False
                raise
            if cur.fetchone() is None:
                raise RuntimeError(f"stage_claims row for {key} disappeared")
            if timed:
                # The wait was for the lock only; the rest of the claim runs with the
                # session's own timeout.
                cur.execute("SET LOCAL lock_timeout TO DEFAULT")
        return True

    def _completion(self, conn: Any, key: StageKey) -> Optional[Completed]:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT completed_by, completed_at FROM {self._completions} "
                "WHERE unit = %s AND stage = %s AND period = %s",
                (key.unit, key.stage, key.period),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Completed(key, row[0], row[1].astimezone(timezone.utc))


def _abort(conn: Any) -> None:
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 - already failing; the server rolls back when the session ends
        pass
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass


class _PostgresClaim:
    """A held claim: the open transaction holding the row lock (``PostgresStageClaim.java:318``)."""

    def __init__(self, conn: Any, completions: str, key: StageKey, claimant: str) -> None:
        self._conn = conn
        self._completions = completions
        self._key = key
        self._claimant = claimant
        self._ended = False
        self._lock = threading.Lock()

    @property
    def key(self) -> StageKey:
        return self._key

    @property
    def claimant(self) -> str:
        return self._claimant

    # PostgresStageClaim.java:341
    def complete(self) -> None:
        with self._lock:
            if self._ended:
                raise RuntimeError(f"claim on {self._key} already ended")
            self._ended = True
            try:
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {self._completions} "
                        "(unit, stage, period, completed_by, completed_at) "
                        "VALUES (%s, %s, %s, %s, clock_timestamp())",
                        (self._key.unit, self._key.stage, self._key.period, self._claimant),
                    )
                self._conn.commit()
            except BaseException as e:
                # The claim has ended, so close() will not release it: release it here.
                _abort(self._conn)
                if isinstance(e, psycopg2.Error):
                    raise RuntimeError(f"PostgreSQL complete failed: {e}") from e
                raise
            self._conn.close()

    # PostgresStageClaim.java:364
    def close(self) -> None:
        with self._lock:
            if self._ended:
                return
            self._ended = True
            # If the rollback fails, the session is already gone: the server rolled the transaction
            # back and released the lock when it ended, so the claim is abandoned either way.
            _abort(self._conn)

    def __enter__(self) -> "_PostgresClaim":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
