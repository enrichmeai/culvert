# Sprint plan — 8 sprints deep

Sprint-0 deliverable. Joseph's directive: line up enough work to keep
agents at full speed for several days, then dispatch wave 1 only after
the plan is locked.

Each sprint is a **human sprint** (2 weeks) that comprises several
**agent dev-sprints** (2h each). Sprint scope below is the agent-work
breakdown — the human sprint envelope absorbs review, merging, and
slack.

## Sprint 0 — Plan + tidy (this sprint)

**Goal:** Backlog refinement, process docs, scaffolding, no production code.

**Deliverables:**
- `docs/framework-evolution/03-dev-process.md` (this session)
- `docs/framework-evolution/04-sprint-plan.md` (this file)
- Parent POM `<modules>` pre-registers sprint-1 modules; reactor builds green
- Placeholder `pom.xml` files in each sprint-1 module dir with
  `<!-- REPLACE THIS ENTIRE FILE -->` hint
- GitHub labels `sprint-2` through `sprint-8` created
- Backlog issues for sprints 2-8 opened with detailed bodies
- Advisor review of the full plan recorded

**Exit criteria:** Joseph signs off; wave 1 of sprint-1 dispatches.

---

## Sprint 1 — Java GCP adapters (Phase B start)

**Branching:** Wave 1 (#5) and wave 2 (#6, #7) landed on `main` directly
before the sprint-branch rule was applied retroactively. Wave 3 (#8, #9)
and the sprint-close UAT run on the `sprint-1` branch; `sprint-1 → main`
PR at sprint close. The mid-sprint rule change is logged in the Sprint 1
retro.

**Goal:** First three GCP contracts on the JVM via Mockito-only tests.

**Tickets:**
- `#5` — secrets-java (`SecretManagerProvider`) [pilot]
- `#6` — bigquery-java `BigQueryWarehouse`
- `#7` — gcs-java (`GcsBlobStore`, 8 methods)
- `#8` — bigquery-java `BigQueryJobControlRepository`
- `#9` — bigquery-java `BigQueryFinOpsSink`

**Dispatch order:**
- Wave 1: `#5` alone (pilot — validates pom conventions, BOM, Mockito-on-GCP)
- Wave 2: `#6` + `#7` parallel
- Wave 3: `#8` + `#9` parallel (same module, different classes)

**Sprint exit gate:**
- All 5 sprint-1 issues closed.
- `mvn -pl data-pipeline-libraries-java -am clean test` green on `main`.
- No `needs-support` or `stop-and-split` labels left on closed issues without a linked follow-up issue.
- Architect posts a sprint-close summary comment on epic #1.

---

## Sprint 2 — Java GCP adapters (Phase B finish)

**Branching:** Standard sprint-branch workflow (DEV_PROCESS.md). Cut
`sprint-2` from `main` after Sprint 1 merges. Each ticket's feature
branch is `feature/issue-N-<slug>` PR'd into `sprint-2`. Single
`sprint-2 → main` PR at sprint close.

**Goal:** Cover the remaining GCP contracts on the JVM so Beam pipelines have a full adapter set.

**Tickets (to be opened in Sprint 0):**
- pubsub-java: `PubSubSource` + `PubSubSink` implementing `Source` / `Sink` over `com.google.cloud.pubsub.v1` clients
- observability-java: `CloudTraceObservabilityHook` + `DataCatalogLineageEmitter`
- tester-java: Mockito-helper library — fixture builders, contract test harnesses for the 11 protocols
- dataflow-java: `DataflowPipeline` implementing `Pipeline` over `DataflowPipelineRunner`

**Exit criteria:** Beam pipeline in `deployments/mainframe-segment-transform-java/` can be re-pointed to use the new adapters end-to-end (no code change yet — just verified-possible).

---

## Sprint 3 — Python Stage 2 (Phase D)

**Goal:** Split GCP-coupled code out of `gcp-pipeline-core` (Python) into named modules, matching the Java module layout.

**Tickets:**
- Extract `gcp_pipeline_core.secrets.*` → new `data-pipeline-gcp-secrets` distribution
- Extract `gcp_pipeline_core.warehouse.bigquery.*` → `data-pipeline-gcp-bigquery`
- Extract `gcp_pipeline_core.blob_store.gcs.*` → `data-pipeline-gcp-gcs`
- Extract `gcp_pipeline_core.pubsub.*` → `data-pipeline-gcp-pubsub`
- Stage 2 closure: rename remaining `gcp-pipeline-core` to `data-pipeline-core` (already-stage-0 done in Python side; this is the public-distribution rename)

**Exit criteria:** Python side matches the Java module layout; deprecation shims point to the new names.

---

## Sprint 4 — Stage 3 decorators + auto-config (Phase E)

**Goal:** First "Spring Boot-style" developer experience surface.

**Tickets:**
- ServiceLoader-based auto-config registry (Java) — `META-INF/services` discovery wired into a `RuntimeContext` builder
- Python equivalent — entry-points-based registry
- `@pipeline` / `@stage` / `@source` / `@sink` decorators (Python)
- First starter project: `data-pipeline-starter-gcp-bigquery` — opinionated bundle (core + bigquery + gcs + secrets + observability)
- Documentation: 5-minute quickstart using the starter

**Exit criteria:** A developer can `pip install data-pipeline-starter-gcp-bigquery` and have a working ingestion pipeline in ≤ 20 lines.

---

## Sprint 5 — Stage 4 contract tests

**Goal:** Catch impl drift via shared contract test suites.

**Tickets:**
- `data-pipeline-contract-tests-java` library — abstract JUnit base classes per contract
- Wire BigQueryWarehouse / GcsBlobStore / SecretManagerProvider into the contract suites
- Python `data-pipeline-contract-tests` — pytest fixtures per Protocol
- CI gating: contract tests run on every PR to any `data-pipeline-gcp-*` module

**Exit criteria:** Any new adapter that fails a contract test fails CI.

---

## Sprint 6 — UAT scaffolding (WireMock for internal demos)

**Goal:** Internal demo harness so Joseph can run end-to-end flows without live GCP.

**Tickets:**
- WireMock fixture set for HTTP-style services (e.g. mock REST gateway, mock auth endpoint)
- Sample full-pipeline test: file-drop on GCS-mock → BigQuery-mock load → audit emission
- `docker-compose.uat.yml` standing up the mocks
- Docs: how to run a UAT demo locally

**Exit criteria:** `make uat-demo` runs a full pipeline end-to-end against mocks in < 60s.

---

## Sprint 7 — Book v1 ship + repo rename (Phase F)

**Goal:** Public release of book v1 + repo rename to reflect the polyglot framework.

**Tickets:**
- Final book-v1 proofread + sample-code cross-check vs the now-renamed packages
- Publish book PDF/EPUB (Leanpub or direct via website)
- Rename GitHub repo `culvert` → `culvert-framework` (engineer decision: confirm exact name before doing it)
- Update all READMEs / docs links / Maven SCM URLs to point at the new repo name
- Publish v1.0.0 of the `data-pipeline-*` Python distributions to PyPI
- Publish 0.1.0 of `com.enrichmeai.culvert:data-pipeline-*` artefacts to Maven Central (via the existing `release` profile)

**Exit criteria:** Anyone can install the framework via `pip` or Maven, follow the book's first chapter, and run a pipeline.

---

## Sprint 8 — Book v2 outline + non-GCP teasers

**Goal:** Prove the cloud-neutral design by sketching AWS / Azure module skeletons.

**Tickets:**
- `data-pipeline-aws-s3-java` skeleton — module structure, README, ONE method implemented (`exists`) so the contract compiles
- `data-pipeline-azure-blob-java` skeleton — same shape
- Book v2 outline document — what changes vs v1, what new chapters (cross-cloud, decorators, contract testing, FinOps, lineage)
- Decision: book v2 timeline + scope-vs-revenue analysis (engineer call)

**Exit criteria:** Joseph has enough information to decide whether v2 is worth the effort and what its scope should be.

---

## Beyond Sprint 8 (not planned, just flagged)

- AWS adapters production-grade (S3 + Glue + Step Functions)
- Azure adapters production-grade (Blob + Synapse + ADF)
- `data-pipeline-gcp-spanner-*` (already on the original GCP roadmap)
- Multi-cloud reference deployment (the Mainframe transform but cloud-portable)
- Conference talk + community building

Joseph picks the next theme based on what landed in sprints 1-8.

## How this file evolves

After each human sprint closes, the architect:
1. Posts the 5-min retro on the sprint's epic issue (see
   `03-dev-process.md` → "5-minute retro at sprint close").
2. Updates the sprint's section here with actual outcomes (links to
   closed issues, retro link, deviations from plan).
3. Re-plans the next two sprints if reality has shifted.
4. Keeps the 8-sprint depth — when sprint N closes, sprint N+8 gets
   added at the bottom.
