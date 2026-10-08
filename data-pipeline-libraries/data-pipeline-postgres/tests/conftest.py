"""A real PostgreSQL for the tests, with the job_control.sql the Java data-pipeline-postgres ships.

Either point ``CULVERT_TEST_POSTGRES_DSN`` at a database you own (its control-plane tables are
truncated), or let the fixture start a throwaway server from the PostgreSQL binaries
(``PG_BIN``, ``pg_ctl`` on PATH, or ``/usr/lib/postgresql/*/bin``). With neither, every test here is
skipped with the reason, never passed.
"""

from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import psycopg2
import pytest

DDL = (Path(__file__).resolve().parents[3] / "data-pipeline-libraries-java" / "data-pipeline-postgres-java"
       / "src" / "main" / "resources" / "com" / "enrichmeai" / "culvert" / "postgres" / "job_control.sql")


def _pg_bin():
    candidates = [os.environ.get("PG_BIN"), os.path.dirname(shutil.which("pg_ctl") or "")]
    candidates += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    for candidate in candidates:
        if candidate and os.path.exists(os.path.join(candidate, "pg_ctl")):
            return candidate
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _skip_or_fail(reason: str) -> None:
    """Skip locally; fail where ``CULVERT_REQUIRE_POSTGRES`` is set (CI), so the suite cannot go
    green with every test skipped."""
    if os.environ.get("CULVERT_REQUIRE_POSTGRES"):
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def server_dsn():
    dsn = os.environ.get("CULVERT_TEST_POSTGRES_DSN")
    if dsn:
        yield dsn
        return
    pg_bin = _pg_bin()
    if pg_bin is None:
        _skip_or_fail("no PostgreSQL: set CULVERT_TEST_POSTGRES_DSN or install the server binaries (PG_BIN)")
    as_root = os.geteuid() == 0
    data = tempfile.mkdtemp(prefix="culvert-pg-test-")
    run_as = ["runuser", "-u", "postgres", "--"] if as_root else []
    if as_root:
        shutil.chown(data, user="postgres")
    port = _free_port()
    subprocess.run(run_as + [f"{pg_bin}/initdb", "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8",
                             "--locale=C"], check=True, capture_output=True)
    subprocess.run(run_as + [f"{pg_bin}/pg_ctl", "-D", data, "-w", "-l", f"{data}/server.log", "-o",
                             f"-p {port} -k {data} -c listen_addresses=127.0.0.1", "start"], check=True,
                   capture_output=True)
    try:
        yield f"host=127.0.0.1 port={port} dbname=postgres user=postgres"
    finally:
        subprocess.run(run_as + [f"{pg_bin}/pg_ctl", "-D", data, "-m", "immediate", "stop"],
                       capture_output=True)
        shutil.rmtree(data, ignore_errors=True)


@pytest.fixture(scope="session")
def schema_applied(server_dsn):
    if not DDL.exists():
        _skip_or_fail(f"job_control.sql not found at {DDL} (the tests read the Java module's copy)")
    conn = psycopg2.connect(server_dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(DDL.read_text(encoding="utf-8"))
    conn.close()
    return server_dsn


@pytest.fixture
def dsn(schema_applied):
    """The database, with the claim tables empty."""
    conn = psycopg2.connect(schema_applied)
    conn.autocommit = True
    with conn.cursor() as cur:
        # A claim an earlier test left open fails this test at once, rather than hanging the run.
        cur.execute("SET lock_timeout = '10s'")
        cur.execute("TRUNCATE job_control.stage_claims, job_control.stage_completions")
    conn.close()
    return schema_applied


def query(dsn: str, sql: str, params=()):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()


def await_lock_wait(dsn: str, application_name: str, seconds: float = 10) -> None:
    """Return once a session tagged ``application_name`` is waiting on a lock (Java:
    ``EmbeddedPostgresLedger.awaitLockWait``)."""
    deadline = time.monotonic() + seconds
    while True:
        rows = query(dsn, "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s "
                          "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()", (application_name,))
        if rows[0][0] > 0:
            return
        if time.monotonic() > deadline:
            raise AssertionError(f"no {application_name} session started waiting on a lock")
        time.sleep(0.005)
