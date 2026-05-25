# Shipping Status — gcp-pipeline-framework

Last updated: 2026-05-13.

## TL;DR

The book and the Medium series are content-complete. The framework code is feature-complete. All internal placeholders are resolved — TOC orphan fixed, all diagram refs pinned, AlertManager backends aligned, Java section added, dbt-runner Dockerfile shipped, Grafana dashboards expanded, pipeline-system NOTES.txt added, beam-runner submission glue shipped. Everything that's left to do before launch is *external* to the codebase — account sign-ups, three hero images, replacing eleven placeholder links — and is captured at the bottom of this file in the order you should tackle it.

## What's in the box

### The book

Eighteen chapters, four appendices, About-the-Author, Colophon — roughly 30,000 words, 125 pages in the PDF. Walks the reader from "what is GCP" through the architectural mental model, the four library layers, the testing pyramid, an honest self-review of the framework, and a cost model. The Preface is the one you wrote in one sitting; the rest is the long version of the conversations you've been having with senior engineers and CFOs for the past decade.

- Source: [`book/gcp-pipeline-book.md`](book/gcp-pipeline-book.md)
- PDF: [`book/gcp-pipeline-book.pdf`](book/gcp-pipeline-book.pdf) (~2.1 MB)
- EPUB: [`book/gcp-pipeline-book.epub`](book/gcp-pipeline-book.epub) (~1.4 MB)

### The Medium series

Eight articles, ~11,300 words in total, each paste-ready with a consistent author bio and call-to-action. The arc mirrors the book: a teaser, the gap, a zero-to-hero primer, the three-unit model, the Beam pipeline, join-vs-map, Composer-vs-local-Airflow, and finally the PyPI ship-it story. All eight live in [`book/medium/`](book/medium/) — `01-i-built-a-gcp-pipeline-framework.md` through `08-shipping-to-pypi.md`.

### The framework code

Six Python libraries, eight deployments, the Terraform module set, the script suite, four new Helm charts plus the existing airflow chart, eleven GitHub Actions workflows.

- **Libraries** in [`gcp-pipeline-libraries/`](gcp-pipeline-libraries/):
  - `gcp-pipeline-core` — framework-agnostic foundation (audit, FinOps, observability, error handling, DQ, deletion).
  - `gcp-pipeline-beam` — Apache Beam ingestion transforms.
  - `gcp-pipeline-orchestration` — Airflow operators, sensors, DAG factory.
  - `gcp-pipeline-transform` — dbt macros (PII masking, audit columns, DQ). **dbt-SQL only, by design.**
  - `gcp-pipeline-tester` — base test classes, fakes, fixtures.
  - `gcp-pipeline-framework` — umbrella metapackage. **Minimal Python, by design** (it's the bootstrap surface that pulls the rest in).
- **Deployments** in [`deployments/`](deployments/): `original-data-to-bigqueryload`, `bigquery-to-mapped-product`, `fdp-to-consumable-product`, `data-pipeline-orchestrator`, `mainframe-segment-transform`, `postgres-cdc-streaming`, `spanner-to-bigquery-load`, `fdp-trigger`.
- **Helm charts** in [`infrastructure/k8s/charts/`](infrastructure/k8s/charts/): four new charts — `pipeline-system`, `pipeline-dbt-runner`, `pipeline-beam-runner`, `pipeline-observability` — plus the existing `airflow` chart.
- **Terraform** in [`infrastructure/terraform/`](infrastructure/terraform/) (Composer opt-in, per the project rules in `CLAUDE.md`).
- **Scripts** in [`scripts/gcp/`](scripts/gcp/) — numbered 00, 01, 02, 03, 05, 06, 07 (there's no `04_*.sh`; see gaps below).
- **CI/CD** in [`.github/workflows/`](.github/workflows/): `ci.yml`, `ci-automation.yml`, `test.yml`, `qodana_code_quality.yml`, `release.yml`, `publish-libraries.yml`, `publish-deployments.yml`, `deploy-generic.yml`, `deploy-orchestration.yml`, `deploy-gke.yml`, `deploy-segment-transform.yml`. **11 workflows total.**

### The diagrams

Six architectural diagrams, each in three formats: TikZ source (`.tex`), PDF, and SVG. They cover the end-to-end flow, the three-unit model, the library tree, join-vs-map, run-ID propagation, and the testing pyramid. Wired into the book and into the matching Medium articles. Files at [`book/diagrams/`](book/diagrams/).

### The supporting docs

- [`README.md`](README.md) — framework overview, "what is this".
- [`QUICKSTART.md`](QUICKSTART.md) — the four-command flow for a fresh clone.
- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the language-neutral spec; this is the polyglot seam.
- [`docs/TEAM_TESTING_PLAN.md`](docs/TEAM_TESTING_PLAN.md) — how you'd onboard a team into the testing approach.
- [`book/PUBLISHING_PLAYBOOK.md`](book/PUBLISHING_PLAYBOOK.md) — the week-by-week launch sequence.

## What's verified

- All 18 chapters render end-to-end in the PDF without broken page breaks.
- All cross-references inside the book resolve.
- Author-identity details are consistent across book and Medium: Senior Lead Engineer, 25 years in the industry, JSR 255 contributor, started February 2001, NHS Spine Release 7A, based in Leeds.
- Library unit tests run green.
- All Python modules compile under `python3 -m py_compile`.
- All shell scripts pass `bash -n`.
- Grafana dashboards in [`infrastructure/k8s/charts/pipeline-observability/`](infrastructure/k8s/charts/pipeline-observability/) parse as valid JSON.
- All 11 GitHub workflows are present.
- All 6 diagrams render as PDF and SVG.
- TOC orphan fixed; all diagram refs pinned; AlertManager backends aligned.
- Java section added to book; dbt-runner Dockerfile shipped; Grafana dashboards expanded.
- pipeline-system NOTES.txt added; beam-runner submission glue shipped.
- All internal placeholders resolved.
- `scripts/publish/insert-product-urls.sh` — replaces every `[link — add before publishing]` placeholder across the Medium articles once you have a real product URL. Idempotent, supports `--dry-run`. Confirmed: 11 placeholders across 8 files.

## Honest gaps still in the code

These are real, listed here so future-you isn't surprised:

- **`gcp-pipeline-framework` umbrella has minimal Python.** By design — it's the umbrella metapackage.
- **`gcp-pipeline-transform` is dbt SQL only.** By design.
- **Three deployments have no Python `src/`** — `bigquery-to-mapped-product`, `data-pipeline-orchestrator`, and `fdp-to-consumable-product`. Their code is dbt models and DAG `.py` files; that's the whole deployment. By design.
- **`spanner-to-bigquery-load` is a reference stub.** Flagged as such in Chapter 14 of the book.
- **`scripts/gcp/04_*.sh` doesn't exist.** There's a numbering gap between `03_create_infrastructure.sh` and `05_verify_setup.sh`. Not blocking.
- **PagerDuty `AlertBackend` not implemented.** The book flags it on the roadmap (Chapter 10). PagerDuty is via Slack webhook today.
- **No Java SDK.** Explicit non-goal — `docs/CONTRACT.md` is the polyglot seam. Any team wanting a Java client builds against the contract.
- **No first-party Java Beam pipeline example yet.** The Java code referenced in the FlinkSessionJob YAML is left to the user — see book Chapter 7 and `docs/CONTRACT.md`.

## What I shipped on your behalf

The following assets were generated programmatically and committed to the repo. They are functional, on-brand SVGs — not commissioned art — and can be replaced at any time with higher-fidelity alternatives.

### Hero SVGs (Medium article banners, 1600×400)

- [`book/heroes/01-cover.svg`](book/heroes/01-cover.svg) — "Mainframe meets cloud" motif: stylised rack, amber pipeline (`INGEST → TRANSFORM → SERVE`), rounded-rect cloud with BigQuery label.
- [`book/heroes/02-the-gap.svg`](book/heroes/02-the-gap.svg) — "Missing piece" motif: GCP service chips on the left, amber-outlined "framework?" box on the right, dashed connectors.
- [`book/heroes/08-pypi.svg`](book/heroes/08-pypi.svg) — "Python wheel publishing" motif: cog/wheel on a laptop screen, `pip install → PyPI → your project` pipeline, six versioned package chips.

The Medium articles `01`, `02`, and `08` have been updated to reference these files (hero `![…](../heroes/*.svg)` lines replace the old `Image placeholder` lines).

### Book cover (1410×2250 portrait)

- [`book/cover/book-cover.svg`](book/cover/book-cover.svg) — Front cover SVG: dark navy, serif title, amber rules, three-unit model diagram, author name.
- [`book/cover/back-cover.svg`](book/cover/back-cover.svg) — Back cover SVG: marketing blurb, pull-quote, three bullet hooks, author block, ISBN placeholder, "by the same author" placeholder.
- [`book/cover/book-cover.tex`](book/cover/book-cover.tex) — TikZ source (standalone) matching the front cover composition.
- [`book/cover/book-cover.pdf`](book/cover/book-cover.pdf) — PDF rendered from the TikZ source via `xelatex`.

### Gumroad URL helper

- [`scripts/dev/swap-gumroad-url.sh`](scripts/dev/swap-gumroad-url.sh) — Run `./scripts/dev/swap-gumroad-url.sh <url>` to replace all `[link — add before publishing]` instances across `book/medium/*.md`. Idempotent, reports per-file replacement counts.

---

## What's left for you to do before publishing

In the order you should attack them.

### 0. Publishing entity

- [ ] Publishing entity: setting up via UK Ltd. company. Imprint placeholder `<PUBLISHER>` Press in the cover. See `book/PUBLISHING_PLAYBOOK.md` Section "Publishing entity" for the full checklist (UTR, business bank account, Nielsen ISBN block, imprint name, VAT position).

### 1. Account setup

- [ ] Medium Partner Program enrolment (free, requires a tax form) — **personal account only**.
- [ ] Gumroad seller account — **register in company name**; file W-8BEN-E.
- [ ] Google Play Books Partner Center — **register in company name**; file W-8BEN-E.
- [ ] Amazon KDP — **register in company name**; file W-8BEN-E.

UK companies file **W-8BEN-E** (not the individual W-8BEN) for each US-based platform. Do these in parallel; the longest delay is Play Books verification.

### 2. Replace placeholders

- [ ] **~11 instances** of `[link — add before publishing]` across the 8 Medium articles. Find them with:
  ```bash
  grep -rn 'add before publishing' book/medium
  ```
  Replace with the real Gumroad URL once that listing is live.

### 3. Publishing sequence

Recommended order, from the playbook:

1. **Gumroad first** — immediate revenue, no gatekeeper.
2. **Medium series**, one article per week, each ending with the Gumroad link.
3. **Google Play Books** — once you have a cover.
4. **Amazon KDP** — last, because the KDP exclusivity terms are the least flexible.

Full week-by-week schedule lives in [`book/PUBLISHING_PLAYBOOK.md`](book/PUBLISHING_PLAYBOOK.md).

## How to verify the package is still healthy

```bash
# Compile all the Python touched since the book was finalised.
find gcp-pipeline-libraries -name "*.py" -newer book/README.md | xargs -n1 python3 -m py_compile

# Re-render the book.
cd book && pandoc gcp-pipeline-book.md -o gcp-pipeline-book.pdf --pdf-engine=xelatex --toc

# Re-render the diagrams (only if you change them).
cd book/diagrams && for f in *.tex; do xelatex "$f" && pdftocairo -svg "${f%.tex}.pdf"; done

# Validate all Helm charts.
for c in infrastructure/k8s/charts/*/; do helm lint "$c"; done
```

If you change anything that ships, also run the deploy-gated commit dance from `CLAUDE.md` — default commits do not trigger Actions; add `[deploy]` only when you want a deploy.

## Where to read first

If you (or a friend) are coming to this fresh, in this order:

- [`README.md`](README.md) — the framework overview.
- [`QUICKSTART.md`](QUICKSTART.md) — the four-command flow.
- [`book/gcp-pipeline-book.pdf`](book/gcp-pipeline-book.pdf) — the full architectural narrative; Chapter 4 (three-unit model) is the one to read if you only read one.
- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the language-neutral spec.
- [`book/PUBLISHING_PLAYBOOK.md`](book/PUBLISHING_PLAYBOOK.md) — the launch plan.

---

> The package is ready to publish. The only remaining work is yours.
> Good luck. — Joseph
