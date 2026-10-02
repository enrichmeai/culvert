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

## The `culvert` command line (`CulvertCli`)

```
culvert runs                                          active runs (created or running), not the history
culvert run <runId>                                   one run
culvert entities --system <id> --date <YYYY-MM-DD>    each entity's latest status
culvert failures --system <id> --date <YYYY-MM-DD>    the failed runs
culvert adapters                                      bound adapters, unbound contracts, load failures
```

Run it with this module, `data-pipeline-core`, `slf4j-api` and your adapter on the classpath:
`java -cp <classpath> com.enrichmeai.culvert.console.CulvertCli adapters`. Exit codes: 0 done,
1 nothing found or no `JobControlRepository` installed, 2 usage error.

- `culvert adapters` lists every provider `AutoConfig` failed to load. `AutoConfig` skips those
  silently, so this is the place to see them.
- **Cost:** every list command reads the whole job-control table on each backend (BigQuery and
  Athena rank it, DynamoDB scans it). There is no watch mode; run it on demand.

The tests run it against the `data-pipeline-tester` fake and print each command's output
(from `data-pipeline-libraries-java`):
`mvn -o -pl data-pipeline-console-java -am test -Dtest=CulvertCliTest -Dsurefire.failIfNoSpecifiedTests=false`
