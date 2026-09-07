# 18 — What GCP provides as a *data product* platform, and what that means for Culvert

**Status:** analysis for review (no tickets yet). **Date:** 2026-09-04. **Source:** BMad architect session (Winston).
**Method:** every GCP product claim below is pinned to a `cloud.google.com` page retrieved **2026-09-04**; every Culvert claim is pinned to `file:line` on `main` at the time of writing. Anything I could not verify is marked **UNVERIFIED** rather than smoothed over.
**Related:** `11-data-mart-cdp-assessment.md` (same genre — assessment against Culvert's capabilities), `02-redesign.md` §§ `GovernancePolicy`/`LineageEmitter` (the ports this analysis lands on), `17-execution-substrates.md` (where Dataform sits).

## TL;DR

GCP has, in the last six months, grown a **first-class `DataProduct` resource** — not a pattern, an actual API/Terraform object with assets, an owner, a contract, access groups, discovery and an access-request workflow. That is precisely the layer Culvert *implies* with ODP → FDP → CDP but has never modelled: Culvert produces **tables in datasets**, not **products with consumers**.

Three findings, in priority order:

1. **F1 — Culvert's GCP lineage story is dead code against a dead API, and silently a no-op today.** `DataCatalogLineageEmitter` (Java *and* Python) writes lineage as **Data Catalog tags**; Data Catalog was deprecated 2025-02-03 with shutdown **2026-06-01** — three months ago. I traced the wiring: **nothing is throwing, because nothing is wired** — the Java `AutoConfig` silently skips it and falls back to `NoOpLineageEmitter`, and the Python entry point loads the class without instantiating it. So this is not an outage; it is worse in a quieter way — a module that advertises GCP lineage and emits nothing, against an API that no longer exists.
2. **F2 — the distribution half of "data product" is a genuine Culvert gap.** Publication, discovery, subscription, access request/approval (Knowledge Catalog data products; BigQuery sharing; clean rooms). Culvert has no concept, no port, no doc. This is the interesting gap — it is where the framework stops and the platform starts.
3. **F3 — GCP's "data contract" is *only* freshness/SLA; Culvert's is *only* shape.** They do not compete, they compose. Culvert's `expected_file_frequency` is the natural join point. This is a cheap, high-value integration, not a rebuild.

**Overall verdict:** GCP's data-product surface is **complementary to Culvert, not competitive with it** — with one exception (lineage), where GCP now gets automatically what Culvert emits manually. Adopt as adapters, publish into it, do **not** let its vocabulary into `docs/CONTRACT.md`.

---

## 0. Naming has moved under us (read this before quoting any older doc)

| Was | Is now | Date | Source |
|---|---|---|---|
| Dataplex Universal Catalog | **Knowledge Catalog** (API, client libs, CLI, IAM names unchanged) | 2026-04-10 *(two sources agree; a search summary quoted 2026-05-26 — I take the two-source date)* | [release notes](https://docs.cloud.google.com/dataplex/docs/release-notes), [deprecations](https://docs.cloud.google.com/dataplex/docs/deprecations) |
| Data Catalog (standalone) | **discontinued** — superseded by Knowledge Catalog | deprecated 2025-02-03, shutdown **2026-06-01** | [deprecations](https://docs.cloud.google.com/dataplex/docs/deprecations) |
| Analytics Hub | **BigQuery sharing** | — | [BigQuery sharing intro](https://docs.cloud.google.com/bigquery/docs/analytics-hub-introduction) |

**Date discrepancy, flagged not resolved:** the Knowledge Catalog *deprecations table* gives Data Catalog shutdown as **2026-06-01**; the older *Data Catalog release notes* say **2026-01-30**. Both are in the past, so F1 stands either way; I have not attempted to establish which turndown actually executed, or whether `datacatalog.googleapis.com` still answers in `joseph-antony-aruja`. **That is a five-minute empirical check and it should be the first thing anyone does with this document.**

---

## 1. The GCP surface, capability by capability

Column 4 is the architect's question, and the only one that matters for planning. Three categories:

- **A — adapter.** Sits cleanly behind an existing Culvert protocol; the GCP concept never leaves `data-pipeline-gcp-*`.
- **B — contract pressure.** Adopting it would push a GCP concept into the language-neutral core (`docs/CONTRACT.md`, `data-pipeline-core`). Needs a deliberate decision, not a drive-by.
- **C — platform, not framework.** Culvert should *target* or *point at* it, never wrap it.

| GCP capability | What it actually gives you | Status (2026-09-04) | Culvert position |
|---|---|---|---|
| **Knowledge Catalog — Data Products** | A logical package: up to 50 assets (BQ tables/views/models, GCS buckets, Iceberg REST resources), owner + contacts, aspects, docs, sample queries, access groups, consumer access requests with approve/reject. Declarative via `google_dataplex_data_product` + `_data_asset` + `_iam`. | **GA 2026-05-25** | **B** — see §3. The packaging layer Culvert lacks. Publish *into* it; do not model it in core yet. |
| **Knowledge Catalog — metadata (entries, aspects, aspect types, glossary)** | Replaces Data Catalog tags/templates. Mapping: tag template → **aspect type** (global), tag → **aspect**, entry group → entry group, custom entry → `GenericEntryType`. | GA; Data Catalog gone | **A** — the correct target for the `GovernancePolicy` GCP adapter (`02-redesign.md:504`), and the migration target for F1. |
| **Data Lineage API** | Central lineage store: processes / runs / lineage events; **automatic** reporting (where ingestion is enabled — it is controllable per org/folder/project) from BigQuery, Dataflow, Cloud Composer, Dataproc/Spark, Vertex AI, Data Fusion; manual reporting + **OpenLineage event import** for anything else. | GA (lineage ingestion control GA 2026-07-17) | **A**, but see F4 — on a GCP substrate most of what Culvert emits is now emitted by the platform for free. |
| **Data quality & profiling scans (Auto DQ)** | Rule-based scans, profiling, historical results, anomaly detection; **rule reusability/templates GA 2026-04-17**; unstructured (PDF/Gemini) profiling in preview. | GA | **A** — already the documented hybrid strategy (`docs/DATA_QUALITY_GUIDE.md:10`). No change of direction needed, only a rename sweep. |
| **BigQuery sharing (ex-Analytics Hub)** | Cross-org/cross-project publication: exchanges, **listings** (description, sample queries, docs), subscribers get an opaque read-only **linked dataset** in their own project/VPC-SC perimeter. No data copy. | GA; Marketplace commercialisation available | **C + gap** — this is the *distribution* half of F2. Culvert has nothing here and arguably should not, beyond making its outputs listing-shaped. |
| **BigQuery data clean rooms** | Sharing sensitive data with owner-defined analysis rules and additional controls. | Preview, all sharing regions | **C** — out of scope. Note it exists so nobody re-invents it under "PII masking". |
| **Dataform / BigQuery pipelines** | Managed SQL workflow engine in BigQuery: table/incremental/view/materialised-view, dependency graph, **assertions** (data quality tests), scheduling. Strict act-as enforced globally; extended access incl. Knowledge Catalog (preview). | GA | **C** — a *substrate choice* alongside dbt, exactly the axis `17-execution-substrates.md` already opened. Not a library concern. |
| **Governance workflows** | Access-management approval flows over catalog resources. | **Preview 2026-07-24** | **C** — watch. Overlaps nothing Culvert owns. |

---

## 2. F1 — dead code against a dead API (and GCP lineage is quietly a no-op)

Culvert ships, in both languages, a `LineageEmitter` implementation that writes **Data Catalog tags** through `datacatalog.v1`:

- Java: `DataCatalogLineageEmitter.java:8-11` — imports `com.google.cloud.datacatalog.v1.{DataCatalogClient, Tag, TagField, CreateTagRequest}`; dependency `google-cloud-datacatalog` via `libraries-bom` 26.39.0 (`pom.xml:36`, `pom.xml:130`).
- Python: `data_catalog_lineage_emitter.py:98` — lazy `from google.cloud import datacatalog_v1`.
- The class's own javadoc already admits the shortcut: *"A dedicated `DataLineagePublisher` backed by the lineage API is deferred to sprint-5"* (`DataCatalogLineageEmitter.java:34-36`). The turndown has overtaken that deferral: the deferred work is no longer "add a config-driven constructor", it is "target a different API".

### Wiring status — traced, because it sets the priority

Nothing in the repo constructs the emitter outside its own tests (`grep "DataCatalogLineageEmitter("` → tests only, both languages). More precisely:

| Path | Behaviour today |
|---|---|
| Java `AutoConfig.discover()` | The class **is** pre-registered in `…/gcp-observability-java/src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.LineageEmitter`, but has no no-arg constructor, so the `ServiceConfigurationError` is swallowed (`AutoConfig.java:90-93`, `AutoConfig.java:226-230`) and `context.lineage()` falls back to `NoOpDefaults.NoOpLineageEmitter` (`DefaultRuntimeContext.java:274-276`). |
| Java direct `ServiceLoader.load(LineageEmitter.class).findFirst()` | **Throws `ServiceConfigurationError`.** The services file says so in its own header comment — a latent trap for anyone bypassing `AutoConfig`. |
| Python `AutoConfig.discover()` | The entry point `lineage = "…:DataCatalogLineageEmitter"` (`pyproject.toml:50`) is loaded but **not instantiated** by design (`autoconfig.py:16-17`). Opt-in construction only. |

**One thing found on the way that outlives this ticket:** the swallow in `loadServiceList` wraps the *entire* `ServiceLoader` iteration in one `catch (Throwable ignored)` (`AutoConfig.java:220-232`). A single un-instantiable provider therefore **truncates the whole list at the point of failure** — it does not skip that one entry and continue. So adding a working `DataLineageEmitter` to a classpath that still carries the broken registration could still yield nothing, depending on iteration order. The comment calls this a sprint-4 limitation awaiting "structured reporting"; it is worth a ticket of its own regardless of the lineage work, because it applies to all sixteen contracts, not just this one.

**So: nothing is burning — but nothing works either.** A GCP deployment that trusts the framework for lineage gets silence, not an error. That is the failure mode I would least like a reader of the book to discover for us. It downgrades F1 from *outage* to *hollow feature + stale claim*, and it means the honest fix is a replacement, not a repair.

### Blast radius of the replacement

Code and packaging (a **public-API removal** from modules already released — `culvert` on PyPI, `com.enrichmeai.culvert:*` on Maven Central; cheap at 0.1.x/0.2.0-SNAPSHOT but it is a breaking change and belongs in `CHANGELOG.md`):

- both implementations + both test classes
- Java `META-INF/services/…LineageEmitter` (delete the pre-registration and its stale sprint-4/5 comment)
- Python `__init__.py` — module docstring **and** the `__all__` export — plus the `pyproject.toml` entry point
- Java `pom.xml:22-23` — the class is named in the module's **published description**
- `data-pipeline-libraries-java/data-pipeline-gcp-observability-java/README.md` (5 refs)
- a cross-reference in `CloudMonitoringMetricsHook.java:32,88`

Docs stating a fact that is now false:

| File | What it claims |
|---|---|
| `docs/framework-evolution/05-book-v2-outline.md:14`, `05-book-v2-outline.md:28` | Data Catalog as a current GCP impl, and `LineageEmitter` "over Data Catalog (GCP)" — in the **book** outline, a product we sell |
| `docs/SECURITY_IAM.md:53`, `:136` | module inventory names Data Catalog |
| `docs/OBSERVABILITY_SPEC.md:75` | "downstream lineage consumers (Data Catalog, compliance)" |
| `docs/DATA_QUALITY_GUIDE.md` (12 refs) | "Dataplex" throughout — renamed to Knowledge Catalog |
| `docs/framework-evolution/02-redesign.md` (10 refs) | plans `data-pipeline-gcp-dataplex` + `DataplexGovernancePolicy` / `DataplexLineagePublisher` |
| `docs/ERROR_HANDLING_GUIDE.md:245`, `docs/SECURITY_CVE.md`, `06-sprint-plan-9-16.md:89`, `docs/interviews/E-Level-Interview-Guide.md:402` | one reference each |

**Recommended fix (one epic, three tickets):**

1. **`DataLineageEmitter`** on the Data Lineage API (processes/runs/lineage events, or OpenLineage import) in both languages — and give it the no-arg constructor the ServiceLoader path needs, the way `CloudTraceObservabilityHook` and `CloudMonitoringMetricsHook` were fixed in Sprint 12 (T12.6, #91). Straight **category A** swap: `LineageEmitter` (`LineageEmitter.java`) does not change, so `docs/CONTRACT.md` does not change and `CONTRACT_VERSION` stays `1.0.0`. That is the abstraction earning its keep — precisely the case `02-redesign.md:517` was written for.
2. **Delete, don't deprecate** the Data Catalog emitters (DoD rule 5 — the API is gone; leaving it is a trap). Note the public-API removal in `CHANGELOG.md`.
3. **Rename + fact sweep** across everything above. On `02-redesign.md`'s planned `data-pipeline-gcp-dataplex`: fix the prose, and keep the artifact id only if it is already published — see §7.

## 3. F2 — the real architectural gap: Culvert has no notion of *publication*

Culvert's data-product hierarchy is a **layering convention over BigQuery datasets** — ODP (raw 1:1), FDP (business-ready), CDP (multi-FDP joins). Everything downstream of "the table exists and passed DQ" is out of frame. There is no owner, no declared consumer, no access request, no discoverability, no listing.

GCP now models all of that natively, and — this is what makes it an architecture question rather than a feature request — **so does every other cloud** (Amazon DataZone / SageMaker Catalog, Microsoft Purview data products). So a `DataProductPublisher` port is *defensible* on Culvert's own cloud-neutral thesis.

**My recommendation is nonetheless: not yet.** Rule of Three. Build **one** GCP implementation, keep it inside `data-pipeline-gcp-*` behind a module-local interface, ship it, and let a second cloud's shape argue for promotion into core. The cost of a premature `DataProductPublisher` in `docs/CONTRACT.md` is a contract major version and a cross-team migration (`CONTRACT.md` §2) — the cost of promoting later is one refactor in one module. Asymmetric; take the cheap mistake.

The trade-off against that: publication is the most *visible* half of "data product" to a reader of the book, and a port declared early is a better story than an adapter bolted on late. If the book's narrative needs the port, that is a legitimate reason to overrule Rule of Three — but it should be an explicit, recorded decision, not a drift.

Note also the honest boundary: **BigQuery sharing/listings and clean rooms are category C.** A framework that generates listings is a framework competing with a console. The most Culvert should do is make its CDP outputs *listing-shaped* (stable dataset, documented schema, sample queries emitted from the EntitySchema) and stop there.

---

## 4. F3 — the two "contracts" are complementary, and the join is already in the schema

| | Culvert `EntitySchema` (`docs/CONTRACT.md` §3`) | Knowledge Catalog data contract |
|---|---|---|
| Governs | **Shape**: fields, dtypes, nullability, PII flags, regex patterns, min/max, primary key | **Service level**: refresh frequency, refresh time, delay threshold (minutes), optional cron |
| Enforced by | The pipeline, at ingest | The catalog, as a published promise to consumers |
| Audience | Producers and implementers | Consumers |

They overlap in exactly one field: `expected_file_frequency` (`DAILY` \| `HOURLY` \| `WEEKLY` \| `ON_DEMAND`) maps onto the contract's *frequency*. That is a genuinely cheap, genuinely useful integration — the EntitySchema JSON already carries the value, so publishing a Knowledge Catalog data product from an EntitySchema is largely mechanical (name, PK, field docs, frequency), and `ON_DEMAND` is the one value with no clean target (**flag it, do not invent a cron**).

Direction I would take: **Culvert owns the shape contract; the catalog owns the service-level contract; Culvert emits the latter from the former.** Nothing new in core. No `CONTRACT_VERSION` bump.

---

## 5. F4 — the uncomfortable one: GCP now gets lineage for free

BigQuery, Dataflow and Cloud Composer report lineage to the Data Lineage API **automatically where ingestion is enabled** (lineage ingestion control went GA 2026-07-17, so it is a per-org/folder/project toggle, not an unconditional given). On the GCP substrate, that is most of Culvert's lineage path (`GCS → Dataflow → BigQuery → dbt`) covered without a single `emit()` call.

That does **not** make `LineageEmitter` redundant, but it does narrow its honest justification to three things — and the docs should say so plainly rather than implying Culvert is the source of GCP lineage:

1. **Non-GCP substrates** — AWS/Azure adapters, and any `17-execution-substrates.md` target the platform does not instrument.
2. **Retention** — platform lineage metadata is retained **30 days**. Culvert's audit/lineage tables in BigQuery are not so limited. For anything compliance-shaped, the framework's store is the system of record and the platform graph is a view.
3. **Business-level edges the platform cannot infer** — a mainframe segment file, an FDP→CDP semantic mapping, a reconciliation chain. Column-level auto-lineage also caps at 1,500 links/job and 20 traversal levels.

Also worth knowing before anyone designs against the graph: traversal caps at 10,000 links per direction.

---

## 6. What I would actually put on the backlog

| # | Ticket | Category | Size | Why now |
|---|---|---|---|---|
| 1 | Empirically confirm the Data Catalog turndown against `joseph-antony-aruja` (does `datacatalog.googleapis.com` still answer?) | — | 15 min | Cheap, zero spend, settles §0's date conflict |
| 2 | `DataLineageEmitter` (Java + Python) on the Data Lineage API, **with** a no-arg ctor for ServiceLoader; delete the Data Catalog emitters + services pre-registration + entry point; `CHANGELOG.md` note for the public-API removal | A | 1 sprint | Turns a hollow feature into a working one; no contract change |
| 3 | Rename + fact sweep: Dataplex→Knowledge Catalog, remove Data Catalog claims — 10 docs plus module README, `pom.xml` description, `__init__.py` | — | ~1 sprint (wider than it looks) | DoD rule 5; a stale doc reads as truth, and one of these is the book |
| 4 | Emit a Knowledge Catalog **data product** from an EntitySchema (GCP module only, no core port) | B→A | 1 sprint | Closes F2's discoverability half at the cheapest altitude |
| 5 | Document the lineage division of labour (auto-where-enabled vs emitted, 30-day retention) in `OBSERVABILITY_SPEC.md` | — | small | F4; prevents an over-claim in the book |
| 6 | Fix `AutoConfig.loadServiceList` to skip per-provider rather than truncating the list on the first `ServiceConfigurationError` (affects all 16 contracts) | — | small | Found while tracing F1; independent of it |
| 7 | ADR: does `DataProductPublisher` belong in core? | B | discussion | Decide deliberately; Rule of Three says wait, the book may say otherwise |

Not proposed, deliberately: wrapping BigQuery sharing/listings, wrapping clean rooms, replacing dbt with Dataform. All category C.

---

## 7. Open questions / UNVERIFIED

- Which Data Catalog turndown date actually executed (2026-01-30 vs 2026-06-01) and whether the endpoint still answers. **§0.**
- Whether `data-pipeline-gcp-dataplex` is published anywhere yet (planned in `02-redesign.md:225`; **no such module exists in either language's tree today** — verified against `data-pipeline-libraries/` and `data-pipeline-libraries-java/`). Affects whether the rename touches a published artifact name.
- Whether the published `culvert` / `com.enrichmeai.culvert` artifacts are at a version where removing a public class is acceptable without a deprecation cycle (I assume yes at 0.1.x — Joseph's call).
- Whether Knowledge Catalog data products expose any **versioning** of product or contract — the docs do not address it, which matters if Culvert publishes on every run.
- AWS/Azure data-product equivalents are asserted from background knowledge, **not verified this session**. Verify before using them as the Rule-of-Three argument in §3.

## Sources (all retrieved 2026-09-04)

- [About data products — Knowledge Catalog](https://docs.cloud.google.com/dataplex/docs/data-products-overview)
- [Create data products](https://docs.cloud.google.com/dataplex/docs/create-data-products)
- [Knowledge Catalog release notes](https://docs.cloud.google.com/dataplex/docs/release-notes)
- [Knowledge Catalog deprecations](https://docs.cloud.google.com/dataplex/docs/deprecations)
- [Transition from Data Catalog to Knowledge Catalog](https://docs.cloud.google.com/dataplex/docs/transition-to-dataplex-catalog)
- [Data Catalog release notes](https://docs.cloud.google.com/data-catalog/docs/release-notes)
- [About data lineage](https://docs.cloud.google.com/dataplex/docs/about-data-lineage)
- [Introduction to BigQuery sharing](https://docs.cloud.google.com/bigquery/docs/analytics-hub-introduction)
- [BigQuery data clean rooms](https://docs.cloud.google.com/bigquery/docs/data-clean-rooms)
- [Dataform overview](https://docs.cloud.google.com/dataform/docs/overview) · [Dataform release notes](https://docs.cloud.google.com/dataform/docs/release-notes)
- [Terraform `google_dataplex_data_product`](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_data_product)
