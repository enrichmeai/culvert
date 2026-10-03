# data-pipeline-postgres (Java)

PostgreSQL adapters for Culvert, starting with `JobControlRepository` (control-plane epic #188,
T2.1). Plain JDBC, so it runs the same on Cloud SQL, RDS or a self-hosted server.

## Set up

1. Apply the DDL once per database. It ships in the jar as
   `com/enrichmeai/culvert/postgres/job_control.sql` and is idempotent:
   `psql "$DATABASE_URL" -f job_control.sql`. No migration tool is chosen; Flyway, Liquibase or
   neither is the deployment's call.
2. Either construct it yourself, with
   `new PostgresJobControlRepository(dataSource)` or with
   `new PostgresJobControlRepository(dataSource, "schema.table")`;
   or let `AutoConfig` find it. To use `AutoConfig`, set these variables (or the matching
   `culvert.postgres.*` system properties):
   - `CULVERT_POSTGRES_URL`, a `jdbc:postgresql://` URL;
   - `CULVERT_POSTGRES_USER`;
   - `CULVERT_POSTGRES_PASSWORD`;
   - `CULVERT_POSTGRES_JOB_CONTROL_TABLE`, optional (default `job_control.pipeline_jobs`).

## How it behaves

- **Append-only, like every backend.** A transition inserts a row, and nothing updates or deletes
  the ledger. Reads rank a run's rows, and the earliest terminal state wins. A failed run stays
  failed: a retry is a new run.
- **Duplicate `createJob` is rejected by the server** (a partial unique index, SQLSTATE 23505).
- **Transitions are serialised per run.** Each one locks the run's opening row, reads, checks and
  appends in one transaction. When several writers race the same transition, exactly one wins.
- `cleanupPartialLoad` deletes from your warehouse table, never from the ledger. Table names
  must be plain `[schema.]table`.

## Tests

`mvn -o -pl data-pipeline-postgres-java -am test` (from `data-pipeline-libraries-java`) starts a
real PostgreSQL 16 server from embedded binaries (`io.zonky.test:embedded-postgres`), with no
Docker. It runs the shared `JobControlRepositoryContractTest` unchanged, plus the adapter's own
tests.
