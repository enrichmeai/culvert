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
`AutoConfig`, never at compile time. **The build enforces this** (#192): a Maven Enforcer
`bannedDependencies` rule in this module's `pom.xml` fails `validate` if any Google Cloud, AWS or
Azure SDK, or any Culvert adapter module, reaches the classpath, directly or transitively.

## The `culvert` command line (`CulvertCli`)

There is no installed `culvert` launcher yet. The tool is the main class
`com.enrichmeai.culvert.console.CulvertCli`, and `culvert <command>` below is shorthand for running
it:

```
culvert runs                                          active runs (created or running), not the history
culvert run <runId>                                   one run
culvert entities --system <id> --date <YYYY-MM-DD>    each entity's latest status
culvert failures --system <id> --date <YYYY-MM-DD>    the failed runs
culvert adapters                                      bound adapters, unbound contracts, load failures
culvert --help
```

To run it from this module (after `mvn -pl data-pipeline-console-java -am install` in
`data-pipeline-libraries-java`), add your adapter's jars to the classpath:

```
cd data-pipeline-libraries-java/data-pipeline-console-java
mvn -q dependency:build-classpath -DincludeScope=runtime -Dmdep.outputFile=cp.txt
java -cp "target/data-pipeline-console-0.3.0.jar:$(cat cp.txt):<your adapter jars>" \
  com.enrichmeai.culvert.console.CulvertCli adapters
```

**Exit codes:**
- **0:** done. An empty list is still 0.
- **1:** one of:
  - the run was not found;
  - no `JobControlRepository` is installed;
  - the backend threw (its exception class and message are printed);
  - `adapters` found providers that failed to load.
- **2:** a usage error.

**What `adapters` shows.** It lists every provider `AutoConfig` failed to load. `AutoConfig` skips
those silently, so this is the place to see them.

**Cost.** Every list command reads the whole job-control table on each backend, and the tool
says so before it reads:
- BigQuery ranks the whole table (`rankedCte`, `BigQueryJobControlRepository.java:726`).
- Athena ranks the whole table (`projection`, `AthenaJobControlRepository.java:551`).
- DynamoDB scans it (`DynamoDbJobControlRepository`, `ScanRequest`).

There is no watch mode; run it on demand.

**Tests.** They run the tool against the `data-pipeline-tester` fake and print each command's
output. From `data-pipeline-libraries-java`:
`mvn -o -pl data-pipeline-console-java -am test -Dtest=CulvertCliTest -Dsurefire.failIfNoSpecifiedTests=false`
