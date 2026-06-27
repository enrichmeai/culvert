# Culvert — the book (v2). Controlling outline & style guide

**This supersedes the v1 book** (`gcp-pipeline-book.md`, about the predecessor
`gcp-pipeline-framework`). Decision (2026-06-27): no point publishing v1; the
GCP implementation is complete and AWS is being built out alongside the writing.
This is the controlling document for the rewrite — chapter-writers work to it.

## Thesis

Culvert is a **cloud-neutral, polyglot data-pipeline framework**: pipelines are
defined once against a language-neutral contract and implemented in the language
that fits the job (Java + Python), with cloud specifics behind adapters. GCP is
the first full implementation; AWS/Azure prove the seam. The book teaches the
*why* (contracts as the portability boundary) and the *how* (the 16 contracts,
their adapters, auto-discovery, contract testing, cost/governance, release).

## Hard rules for every chapter (non-negotiable)

1. **Ground every technical claim in real source — cite `path:line`.** Do not
   invent APIs, class names, method signatures, or numbers. If you describe
   `BudgetGovernancePolicy.check_budget`, it must exist; quote it. Pricing/config
   numbers come from the code, not memory.
2. **Honest status.** Java reactor is at `1.0.0`, **built and frozen at tag
   `java-1.0.0`, not yet published**. Python parity is in progress. Nothing is on
   Maven Central or PyPI yet; the release is a coordinated future step. Never
   imply it's shipped.
3. **Brand & names.** Product = **Culvert**. Java groupId `com.enrichmeai.culvert`;
   Python distributions currently `data-pipeline-*` (the `culvert` PyPI name is
   reserved for the coordinated release). The predecessor `gcp-pipeline-framework`
   is **deprecated in place**, referenced only as "what came before."
4. **Code examples must compile/run in spirit** — drawn from real packages
   (`data-pipeline-core`, the GCP adapters), not pseudo-code that contradicts the
   API. Prefer short excerpts that mirror actual tests.
5. **Consistent terminology** (see glossary below). One term per concept.
6. **Voice:** first-person practitioner, concrete, no marketing fluff. Match the
   v1 book's readable engineering tone, applied to the Culvert architecture.

## Chapter plan

| # | Chapter | Core content | Primary source to ground in |
|---|---|---|---|
| Preface | Who this is for, what changed from v1 | — | this outline |
| 1 | **Why Culvert** — the gap, cloud-neutral + polyglot thesis | the portability problem; contracts as the boundary | `docs/CONTRACT.md`, `docs/framework-evolution/02-redesign.md` |
| 2 | **The contract** — the language-neutral spec | what a contract is; the 16 + `StageMetrics`; one spec, two languages | `docs/CONTRACT.md`, `data-pipeline-core-java/.../contracts/`, `data-pipeline-core/.../contracts/` |
| 3 | **The Protocol set by family** | storage / compute / operational / config primitives | the contract interfaces (both languages) |
| 4 | **Polyglot by design** | Java vs Python boundary; Dataflow=Java; dbt+orchestration reused | `docs/framework-evolution/13-python-parity-release.md` (division of labour) |
| 5 | **GCP — the first full implementation** | the adapters: BigQuery/GCS/PubSub/Secrets/Observability/Dataflow | `data-pipeline-gcp-*-java` + `data-pipeline-gcp-*` |
| 6 | **Cross-cloud** | the adapter seam; AWS S3 + Azure Blob skeletons; building out (in progress) | `data-pipeline-aws-s3-java`, `data-pipeline-azure-blob-java` |
| 7 | **Auto-config & discovery** | ServiceLoader (Java) / entry-points (Python); `AutoConfig.discover()` | `autoconfig.py`, Java `AutoConfig` |
| 8 | **Contract testing as the safety net** | abstract/mixin contract tests; binding adapters; proving conformance | `data-pipeline-contract-tests*` |
| 9 | **Cost & governance** | FinOps cost trackers + `BudgetGovernancePolicy`; PII masking; data quality | `finops_api/`, `governance_api/`, `dataquality/` |
| 10 | **Observability & lineage** | Cloud Trace / Cloud Monitoring / Data Catalog; `StageMetricsHook` | `data-pipeline-gcp-observability*` |
| 11 | **Orchestration** | cloud-neutral DAG model + Airflow/Composer renderers; Airflow reuse | `data-pipeline-orchestration-java`, Python `data-pipeline-orchestration` |
| 12 | **Shipping Culvert** | coordinated Maven Central + PyPI; the build-and-hold gate; deprecating the predecessor | `docs/framework-evolution/13-python-parity-release.md` |

## Glossary (canonical terms)

- **Contract** — a language-neutral interface (Java interface / Python Protocol) every adapter implements.
- **Adapter** — a cloud/tech-specific implementation of a contract (e.g. `GcsBlobStore`).
- **Reactor** — the Java Maven multi-module build.
- **Auto-config / discovery** — `AutoConfig.discover()` finding installed adapters via ServiceLoader (Java) / entry-points (Python).
- **Coordinated release** — publishing Java (Maven Central) and Python (PyPI `culvert`) together, gated on both being ready.

## Process

Rewrite runs as dispatched waves (one agent per chapter), each grounded per the
hard rules, then an architect coherence pass (terminology, cross-references,
status consistency). Predecessor v1 files are replaced; the Medium series is
rewritten last, derived from the finished chapters. The old
`docs/framework-evolution/05-book-v2-outline.md` is superseded by this document.
