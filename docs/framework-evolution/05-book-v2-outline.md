# Book v2 outline — DRAFT

**Status:** Draft outline. Joseph reviews / edits / accepts. Sprint-8 deliverable.

Book v1 is the "publishing the book" track that exists separately from this framework codebase. This outline assumes v1 ships first (against the framework's v0.1.0 release per [CHANGELOG.md](../../CHANGELOG.md)) and proposes what v2 adds.

## What changed between v1 and v2

| Theme | v1 status | v2 plan |
|---|---|---|
| Brand | Culvert + `data-pipeline-*` artefacts established | Same. v2 builds on that. |
| Cloud coverage | GCP-only impls (BigQuery, GCS, Pub/Sub, Dataflow, Cloud Trace, Data Catalog, Secret Manager) | Adds AWS (S3 onwards) + Azure (Blob onwards). Sprint-8 skeletons prove the pattern; v2 expands. |
| Decorators / auto-config | Sprint-4 introduces `@pipeline / @stage / @source / @sink / @transform` (Python) + `AutoConfig` (Java + Python) | Adds config-driven instantiation (planned sprint-9): adapters wire themselves from `culvert.yaml`. |
| Contract tests | Sprint-5 abstract test classes | Adapters wired in; CI gating ensures any new adapter passes the same baseline. |
| UAT / demo harness | Sprint-6 WireMock for HTTP-style services | Adds: sample wired pipeline + `make uat-demo` target running end-to-end mocks in < 60s. |

## Proposed new chapters

1. **Why cloud-neutral?** Restate the case using the v0.1.0 evidence — same Java code runs against GCP / AWS / Azure with adapter swap. Sprint-8 S3 + Azure Blob skeletons as worked examples.
2. **The Protocol set, one chapter per family** (3-4 chapters total):
   - Storage primitives — `BlobStore`, `Source`, `Sink`
   - Compute primitives — `Warehouse`, `Pipeline`, `PipelineStage`, `Transform`
   - Operational primitives — `JobControlRepository`, `ObservabilityHook`, `LineageEmitter`, `AuditEventPublisher`, `GovernancePolicy`
   - Configuration primitives — `SecretProvider`, `FinOpsSink`, `RuntimeContext`
3. **Polyglot patterns** — when does the Java vs Python boundary matter? When is a Beam pipeline (Java) appropriate vs a Python orchestrator + adapter? Use the Sprint 1+2 Java work and Sprint 3 Python work as parallel case studies.
4. **Cross-cloud lineage and FinOps** — write once, read in three clouds. `LineageEmitter` over Data Catalog (GCP) / OpenLineage (cloud-neutral) / Purview (Azure). `FinOpsSink` over BigQuery, Athena, or Synapse with the same call site.
5. **Auto-config and decorators in practice** — show the Sprint 4 surface evolving into the Sprint 9 (planned) config-driven instantiation.
6. **Contract testing as the safety net** — Sprint 5 contract test classes; how to add a new adapter and prove it conforms before merging.
7. **WireMock for UAT** — when to use it (HTTP-style services around the framework) vs when not to (gRPC SDKs use Mockito). Sample full-pipeline demo.

## What stays unchanged from v1

- The framework's basic shape — eleven Protocols + adapter modules.
- The Culvert brand. The `data-pipeline-*` artefact convention.
- The development process (orchestrator / advisor / dev-agent roles, sprint-branch workflow, 5-minute retros).

## Decision-required items

These are Joseph's calls, not orchestrator-determinable:

- **Scope vs revenue.** A multi-cloud book is more material than v1; is the audience expansion worth the effort?
- **Timeline.** v2 is plausibly a 6-month project; ship after v1 stabilises (3 months in market?) or run them in parallel?
- **Co-author vs solo.** Cross-cloud expertise benefits from multiple voices.
- **Platform.** Stay on the v1 platform (Leanpub / direct / etc.) or move to a publisher for v2?

## Tracking

This outline document is the only sprint-8 deliverable on the book front. Subsequent work happens off-codebase (Word/Markdown manuscript, editor, publisher) and is not tracked in this repo beyond status pointers.

## Not in scope for this outline

- Per-chapter word counts, schedules, milestones — that's Joseph's planning.
- Specific code examples — those grow out of the framework as it stabilises.
- Marketing copy. Outline is technical-content-only.
