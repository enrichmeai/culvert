# data-pipeline-postgres (Python)

PostgreSQL adapters for Culvert's Python side. Today: `PostgresStageClaim`, the Python
`StageClaim` (#196). It is the twin of the Java `PostgresStageClaim`
(`data-pipeline-libraries-java/data-pipeline-postgres-java`): **the same statements on the same
tables**, so Java and Python claimants lock the same rows and contend for the same stages. That
follows from the identical SQL; no test yet runs a Java and a Python claimant against each other.

```python
from datetime import timedelta
from data_pipeline_core import Acquired, Completed, StageKey
from data_pipeline_postgres import PostgresStageClaim

claims = PostgresStageClaim()          # CULVERT_POSTGRES_URL, _USER, _PASSWORD
result = claims.try_claim(StageKey("orders", "load", "2026-10-06"), "worker-1", timedelta(0))
if isinstance(result, Acquired):
    with result.claim as claim:        # an exception abandons the claim
        ...                            # do the stage's work
        claim.complete()               # the stage never runs again under this key
elif isinstance(result, Completed):
    ...                                # already done by result.completed_by
else:
    ...                                # Held: another worker has it
```

- **A claim is a row lock held by an open transaction.** If the claimant dies, its session ends,
  and the server releases the lock. A claim holds one connection for the whole stage.
- **Set** `idle_in_transaction_session_timeout` **and TCP keepalives** on the server, so a hung but
  connected claimant's session is ended too. The timeout must be longer than the longest stage.
- **Settings:** `CULVERT_POSTGRES_URL` is a libpq connection string or the Java
  `jdbc:postgresql://host:port/db` form, read as `postgresql://host:port/db`. JDBC-only parameters
  such as `ApplicationName` are not accepted. `CULVERT_POSTGRES_USER` and
  `CULVERT_POSTGRES_PASSWORD` are optional. You can also pass your own `connect` callable.
- **Tables:** they come from the `job_control.sql` that the Java `data-pipeline-postgres` ships.
  Apply it once per database.
- **A rendered DAG's stage gate** calls `completion(unit=, stage=, period=)`. Wrap the claim in
  `data_pipeline_core.stage_claim_api.CompletionChecker` for it.

Installed with `pip install culvert[postgres]`, which brings `psycopg2-binary`. AutoConfig finds it
under the `stage_claim` entry point.

## Tests

```bash
python3 -m venv /tmp/vw && /tmp/vw/bin/pip install -q -e data-pipeline-libraries/data-pipeline-core \
  -e data-pipeline-libraries/data-pipeline-contract-tests -e "data-pipeline-libraries/data-pipeline-postgres[test]"
/tmp/vw/bin/python -m pytest data-pipeline-libraries/data-pipeline-postgres/tests -q
```

- **The server:** they run against a real PostgreSQL. Set `CULVERT_TEST_POSTGRES_DSN`, or let the
  fixture start a throwaway server from the binaries (`PG_BIN`, `pg_ctl` on `PATH`, or
  `/usr/lib/postgresql/*/bin`). With neither, they skip, with the reason given.
- **The schema:** they read the Java module's `job_control.sql` from this repository.
- **What runs:** the shared `StageClaimContract`, a test-for-test mirror of the Java
  `StageClaimContractTest`, including the deterministic two-connection contention cases. Then the
  PostgreSQL cases of `PostgresStageClaimTest.java`, except its pooled-connection `completion` case:
  the Python adapter opens a new connection for every call, so it has no pooled connection to
  leave idle.
- **In CI:** `CULVERT_REQUIRE_POSTGRES=1` turns the skip into a failure.
