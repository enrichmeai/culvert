"""The stores the rendered reference DAG reads, on PostgreSQL (#232).

``dags/reference_e2e_control_plane.py`` takes its three stores from this module:

- ``stage_claim().completion(unit=, stage=, period=)``: the completion row from
  ``job_control.stage_completions``, or ``None`` (the Python side of ``StageClaim.completion``).
- ``input_readiness().not_ready(unit=, period=)``: one ``"<input>=<STATE> (<run>)"`` string per
  expected input that is not ready, a non-empty list when the unit declares nothing, and an empty
  list only when every input is ready. It ports ``ReadinessResolver``'s rule; the proof harness
  checks it against the Java answer on the same rows (scenario 5).
- ``job_control()``: **a stub.** It records nothing. The DAG's job-control calls go through it so the
  task callables run; ``CULVERT_PROOF_TASK_SECONDS`` makes each call sleep, which gives every task a
  duration for scenario 6 to sample. Job control is proved on the Java workers (scenario 7).

It is a harness module, not a Culvert library. Culvert ships no Python ``InputReadiness``, so
``input_readiness()`` is its own. ``stage_claim()`` could be Culvert's Python ``PostgresStageClaim``
(#196) wrapped in ``CompletionChecker``; the harness keeps its own one-statement read so that it needs
only psycopg2 on the workers. It only reads the control-plane tables.

**Where the database is** (#234). Either:

- ``CULVERT_POSTGRES_DSN``, a libpq connection string: the local proof, and the harness's own
  Python parity check; or
- what the control-plane Terraform gives a Cloud Composer environment: ``CULVERT_POSTGRES_HOST``,
  ``CULVERT_POSTGRES_DB``, ``CULVERT_POSTGRES_USER``, and ``CULVERT_POSTGRES_PASSWORD_SECRET``, a
  Secret Manager secret's resource name (``projects/<p>/secrets/<name>``), whose latest version is
  read with the worker's own credentials (``google-cloud-secret-manager``, which Composer images
  carry). The connection then uses ``sslmode=require``, as the Terraform's ``jdbc_url`` does.
"""

import os
import time

import psycopg2

SCHEMA = "job_control"


_COMPOSER_SETTINGS = ("CULVERT_POSTGRES_HOST", "CULVERT_POSTGRES_DB", "CULVERT_POSTGRES_USER",
                      "CULVERT_POSTGRES_PASSWORD_SECRET")
_password = None


def _secret(name):
    """The latest version of a Secret Manager secret, read once per process."""
    global _password
    if _password is None:
        from google.cloud import secretmanager  # only on Composer: the local proof never imports it
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=name + "/versions/latest")
        _password = response.payload.data.decode("utf-8")
    return _password


def connect_kwargs(env=None, secret=None):
    """The ``psycopg2.connect`` arguments, from the environment (see the module docstring)."""
    env = os.environ if env is None else env
    secret = _secret if secret is None else secret
    dsn = env.get("CULVERT_POSTGRES_DSN")
    if dsn:
        return {"dsn": dsn}
    missing = [k for k in _COMPOSER_SETTINGS if not env.get(k)]
    if missing:
        raise RuntimeError(
            "reference_e2e_control_plane_stores needs CULVERT_POSTGRES_DSN, or all of "
            + ", ".join(_COMPOSER_SETTINGS) + " (missing: " + ", ".join(missing) + ")")
    return {
        "host": env["CULVERT_POSTGRES_HOST"],
        "dbname": env["CULVERT_POSTGRES_DB"],
        "user": env["CULVERT_POSTGRES_USER"],
        "password": secret(env["CULVERT_POSTGRES_PASSWORD_SECRET"]),
        "sslmode": "require",
    }


def _connect():
    return psycopg2.connect(**connect_kwargs())


def _query(sql, params):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


class _StageClaim:
    def completion(self, unit, stage, period):
        rows = _query(
            "SELECT completed_by, completed_at FROM " + SCHEMA + ".stage_completions "
            "WHERE unit = %s AND stage = %s AND period = %s",
            (unit, stage, period),
        )
        return rows[0] if rows else None


def resolve(expected, attempts):
    """``ReadinessResolver.resolve`` in Python.

    ``expected`` is the set of input names; ``attempts`` the period's rows in ledger order, each
    ``(input, run_id, state, retry_of)``. Returns ``{input: (STATE, run_id or None)}``.
    """
    out = {}
    for name in sorted(expected):
        first_seen = {}
        terminal = {}
        links = {}
        for index, (input_name, run_id, state, retry_of) in enumerate(attempts):
            if input_name != name:
                continue
            first_seen.setdefault(run_id, index)
            if state in ("validated", "failed") and run_id not in terminal:
                terminal[run_id] = state  # within an attempt, the earliest terminal event wins
            if retry_of:
                links.setdefault(run_id, retry_of)  # an attempt's first link is the one that counts
        superseded = set()
        for run_id, retry_of in links.items():
            # A retry supersedes only an attempt recorded before it.
            if retry_of in first_seen and first_seen[retry_of] < first_seen[run_id]:
                superseded.add(retry_of)
        standing = sorted((r for r in first_seen if r not in superseded), key=first_seen.get)
        failed = [r for r in standing if terminal.get(r) == "failed"]
        pending = [r for r in standing if r not in terminal]
        validated = [r for r in standing if terminal.get(r) == "validated"]
        if failed:
            out[name] = ("FAILED", failed[0])
        elif pending:
            out[name] = ("PENDING", pending[0])
        elif validated:
            out[name] = ("READY", validated[0])
        else:
            out[name] = ("MISSING", None)
    return out


class _InputReadiness:
    def expected(self, unit, period):
        rows = _query(
            "SELECT period, input FROM " + SCHEMA + ".readiness_expected "
            "WHERE unit = %s AND period IN (%s, '')",
            (unit, period),
        )
        own = {i for p, i in rows if p == period}
        return own if own else {i for p, i in rows if p == ""}

    def not_ready(self, unit, period):
        expected = self.expected(unit, period)
        if not expected:
            return ["no expected inputs are declared for unit '%s'" % unit]
        attempts = _query(
            "SELECT input, run_id, state, retry_of FROM " + SCHEMA + ".readiness_attempts "
            "WHERE period = %s AND input = ANY(%s) ORDER BY seq",
            (period, list(expected)),
        )
        resolved = resolve(expected, attempts)
        return [
            "%s=%s%s" % (name, state, " (%s)" % run if run else "")
            for name, (state, run) in sorted(resolved.items())
            if state != "READY"
        ]


class _JobControlStub:
    def __getattr__(self, name):
        def call(**kwargs):
            seconds = float(os.environ.get("CULVERT_PROOF_TASK_SECONDS", "0"))
            if seconds:
                time.sleep(seconds)
        return call


def stage_claim():
    return _StageClaim()


def input_readiness():
    return _InputReadiness()


def job_control():
    return _JobControlStub()
