# data-pipeline-console (Java)

Read-only operator views over `JobControlRepository`, for any backend. Control-plane epic #188,
Phase 1.

- `ConsoleReadService` wraps the five read methods: a run, the pending runs, the entity status
  board, the failures, and an FDP model's status for a system and extract date. It never calls a
  write method, and never `cleanupPartialLoad`, which deletes data.
- Views (`RunView`, `EntityStatusView`, `FailureView`, `FdpRunView`) mirror the contract records.
  A failed run stays failed: a retry is another run with its own run id.
- Get one with `ConsoleReadService.from(AutoConfig.discover())`. The `JobControlRepository` comes
  from whichever adapter is on the classpath (BigQuery, DynamoDB, Athena).

**This module binds only to Culvert contracts.** It depends on `data-pipeline-core` and nothing
cloud-specific, so the same views work on every backend. Adapters arrive at runtime through
`AutoConfig`, never at compile time.
