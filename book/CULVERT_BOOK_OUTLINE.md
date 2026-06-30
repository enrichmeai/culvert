# Culvert — the book. Controlling outline, structure & agent brief

**The book becomes the Culvert book** (decision 2026-06-28). Culvert is the
protagonist; the **GCP-origin journey is the narrative spine** — we started with
one real cloud (GCP), found most of the code was already cloud-neutral, extracted
contracts, and arrived at a cloud-neutral polyglot framework (the Spring
precedent, told as lived experience). The v1 manuscript (`gcp-pipeline-book.md`)
is the raw material: memoir-grade, in Joseph's voice, with **Chapter 23 already
the Culvert story**. We reposition and extend it; we do not discard it.

**Authorship:** agents *draft* → architect *integrates* (coherence + technical
verification) → **Joseph owns the final voice**. Agents adapt Joseph's existing
prose for voice and ground every technical claim in real source.

## Thesis

Culvert is a **cloud-neutral, polyglot data-pipeline framework**: define a pipeline
once against a language-neutral contract; implement it in the language that fits
(Java + Python); keep cloud specifics behind adapters. GCP is the first full
implementation (real, shipping in this repo); AWS/Azure skeletons prove the seam.

## Non-negotiable standards (every chapter)

1. **Voice** — first-person practitioner; war stories; earned opinions; British
   spelling. Adapt the nearest v1 passage; do not invent a flatter tone. (The
   first agent attempt produced technically-correct but voiceless chapters — that
   bar is a failure, not a draft.)
2. **Build conventions** — pandoc-flavoured markdown: `\begin{takeaways}…\end{takeaways}`
   boxes (one per chapter), `\newpage` between chapters, `\index{}` where v1 uses it,
   real code fences. Must compile through `book/*.tex`.
3. **Technical grounding** — every API/name/number cites real source `path:line`.
   No invented APIs. Honest status: **Culvert is built & held, nothing published**
   (coordinated Maven Central + PyPI `culvert` is future). Predecessor
   `gcp-pipeline-framework` = deprecated-in-place, referenced only as origin.
4. **Canonical names** — see glossary.

## Structure (Culvert-first, GCP-origin arc)

Per chapter: **[src]** = v1 chapter to adapt for voice; **[ground]** = Culvert source for facts.

### Part I — The case
- **Preface** — [src: v1 Preface] (already Culvert-aware)
- **1 Why Culvert / why this book** — gap + culvert metaphor + the "start with GCP" thesis [src: v1 Ch1 + Ch23 opening]
- **2 The landscape and the gap** [src: v1 Ch2]
- **3 GCP fundamentals, zero to hero** — the concrete first cloud [src: v1 Ch3]

### Part II — The contract (the heart) — write FIRST
- **4 Contracts as the portability boundary** — cloud-neutral audit + Spring precedent as the GCP-origin story [src: v1 Ch23 §why-rename/§Spring-precedent/§what-was-already-cloud-neutral]
- **5 The contract set** — 16 interfaces + `StageMetrics`, by family [ground: `data-pipeline-core-java/.../contracts/`, `data-pipeline-core/.../contracts/`; raw input: drafted `book-ch2`/`book-ch3` branches (fact-checked, reuse content, rewrite for voice)]
- **6 Polyglot by design** — Java+Python division of labour [ground: `docs/framework-evolution/13-python-parity-release.md`]

### Part III — The first implementation (GCP)
- **7 Storage & messaging adapters** (GCS, Pub/Sub) [src: v1 Ch6/Ch7; ground: `data-pipeline-gcp-gcs`, `-pubsub`]
- **8 Warehouse & job control** (BigQuery) [ground: `data-pipeline-gcp-bigquery`]
- **9 Execution — Beam on Dataflow** (Java) [src: v1 Ch7; ground: `data-pipeline-gcp-dataflow-java`]
- **10 Transformation — dbt** (reused) [src: v1 Ch8; ground: `data-pipeline-transform`]
- **11 Orchestration** — cloud-neutral DAG model + Airflow/Composer [src: v1 Ch9; ground: `data-pipeline-orchestration-java`, py `data-pipeline-orchestration`]

### Part IV — Production concerns (largely cloud-neutral; strong v1 reuse)
- **12 Observability & lineage** [src: v1 Ch11; ground: `data-pipeline-gcp-observability`]
- **13 Cost & FinOps** [src: v1 Ch11 FinOps; ground: `finops_api`, cost trackers, `BudgetGovernancePolicy`]
- **14 Governance, masking, data quality** [src: v1 Ch18; ground: `governance_api`, `dataquality`]
- **15 Auto-config & discovery** [ground: `autoconfig.py`, Java `AutoConfig`]
- **16 Contract testing as the safety net** [src: v1 Ch12; ground: `data-pipeline-contract-tests*`]
- **17 CI/CD and the coordinated release** — reframed to Maven Central + PyPI `culvert` [src: v1 Ch15; ground: `docs/framework-evolution/13`]

### Part V — Beyond GCP & the road ahead
- **18 Cross-cloud — the adapter seam** (AWS S3 / Azure Blob skeletons; building out, honest) [ground: `data-pipeline-aws-s3-java`, `data-pipeline-azure-blob-java`]
- **19 An honest code review** (keep the device, applied to Culvert) [src: v1 Ch17]
- **20 Working with AI coding agents** — now lived, not hypothetical (the multi-agent SDLC) [src: v1 Ch21 + `CLAUDE.md`]
- **21 Getting started & roadmap** [src: v1 Ch22 + Ch23 close]

### Appendices — adapt v1
Contract reference; directory map; cost model; glossary; **About the Author** (keep ~verbatim); further reading; colophon.

## Glossary (canonical terms)

- **Contract** — language-neutral interface (Java interface / Python Protocol) every adapter implements.
- **Adapter** — cloud/tech-specific implementation of a contract (e.g. `GcsBlobStore`).
- **Reactor** — the Java Maven multi-module build.
- **Auto-config / discovery** — `AutoConfig.discover()` finding installed adapters via ServiceLoader (Java) / entry-points (Python).
- **Coordinated release** — publishing Java (Maven Central) and Python (PyPI `culvert`) together, gated on both being ready.

## Agent brief template (per chapter)

> You are drafting one chapter of the Culvert book. Worktree: <path> (work only here).
> Read `book/CULVERT_BOOK_OUTLINE.md` (obey its standards).
> **Voice:** adapt the v1 source passage `<book/gcp-pipeline-book.md lines …>` —
> keep Joseph's first-person voice, war-story cadence, British spelling. Do not
> flatten it into documentation.
> **Ground:** every technical claim cites real source `<paths>` as `path:line`;
> no invented APIs; honest unpublished status.
> **Format:** pandoc markdown; `# Chapter N — Title`; one `\begin{takeaways}` box;
> end with `\newpage`. Write to `book/chapters/NN-title.md`.
> Commit + push your branch. Return: file path, the v1 passage adapted, key
> sources cited (path:line), any flag.

Then: architect verifies citations independently, normalises voice/cross-refs,
assembles into the master manuscript. Joseph does the final voice pass.

> The old `docs/framework-evolution/05-book-v2-outline.md` is superseded by this document.
