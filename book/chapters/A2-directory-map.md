# Appendix B — Directory Map

The layout below reflects the repository as it stands at v0.1.0 — built and held, not yet published to Maven Central or PyPI. The structure has two active library trees (Java and Python) and one legacy tree that is being retired.

Source of truth: `README.md:29–47`.

```
culvert/                              # repo root (codename; customer brand: Valuedocs Legal)
├── README.md
├── VERSION
├── pyproject.toml
├── reconstruct.py
├── qodana.yaml
│
├── data-pipeline-libraries-java/     # Java reactor — Maven, groupId com.enrichmeai.culvert
│   ├── pom.xml                       # parent POM (13 modules)
│   ├── data-pipeline-core-java       # contracts + records + AutoConfig (ServiceLoader)
│   ├── data-pipeline-gcp-bigquery-java
│   ├── data-pipeline-gcp-gcs-java
│   ├── data-pipeline-gcp-pubsub-java
│   ├── data-pipeline-gcp-secrets-java
│   ├── data-pipeline-gcp-observability-java
│   ├── data-pipeline-gcp-dataflow-java
│   ├── data-pipeline-aws-s3-java     # cloud-neutrality skeleton (not yet complete)
│   ├── data-pipeline-azure-blob-java # cloud-neutrality skeleton (not yet complete)
│   ├── data-pipeline-orchestration-java  # DagSpec/TaskSpec + Airflow/Composer renderers
│   ├── data-pipeline-contract-tests-java
│   ├── data-pipeline-tester-java
│   └── data-pipeline-it-support-java
│
├── data-pipeline-libraries/          # Python library set
│   ├── data-pipeline-core            # Protocols + records + AutoConfig (entry-points)
│   ├── data-pipeline-gcp-bigquery
│   ├── data-pipeline-gcp-gcs
│   ├── data-pipeline-gcp-pubsub
│   ├── data-pipeline-gcp-secrets
│   ├── data-pipeline-gcp-observability
│   ├── data-pipeline-orchestration
│   ├── data-pipeline-transform       # dbt is SQL + macros; no Java twin by design
│   ├── data-pipeline-tester
│   ├── data-pipeline-contract-tests
│   └── data-pipeline-framework       # umbrella: installs all sibling packages
│
├── deployments/                      # reference pipelines built on the framework
│   ├── original-data-to-bigqueryload/    # ingestion (Beam)
│   ├── bigquery-to-mapped-product/       # FDP transform (dbt)
│   ├── fdp-to-consumable-product/        # CDP transform (dbt)
│   ├── data-pipeline-orchestrator/       # DAGs (Airflow)
│   ├── mainframe-segment-transform/      # FDP → mainframe (Beam, Python)
│   ├── mainframe-segment-transform-java/ # FDP → mainframe (Beam, Java)
│   ├── spanner-to-bigquery-load/         # federated (dbt)
│   ├── postgres-cdc-streaming/           # streaming reference (Beam)
│   ├── fdp-trigger/                      # downstream notification
│   └── reference-e2e-gcp/                # end-to-end GCP smoke suite
│
├── docs/                             # 30+ design and operations guides
│   └── framework-evolution/          # canonical "why / what / when" for the redesign
│       ├── 01-audit.md               # cloud-neutral audit that started it all
│       ├── 02-redesign.md
│       ├── 03-dev-process.md
│       ├── 04-sprint-plan.md
│       ├── 06-sprint-plan-9-16.md
│       ├── 10-architecture.md
│       └── 13-python-parity-release.md   # polyglot release gate spec
│
├── book/                             # this manuscript
│   ├── CULVERT_BOOK_OUTLINE.md
│   ├── gcp-pipeline-book.md          # v1 raw material (memoir-grade prose)
│   ├── gcp-pipeline-book.pdf / .epub / .tex
│   └── chapters/                     # drafted chapters (one file per chapter)
│
├── infrastructure/
│   └── terraform/                    # GCP infrastructure-as-code
│       ├── main.tf
│       ├── security.tf
│       ├── dataflow.tf
│       └── systems/generic/
│           ├── ingestion/
│           ├── transformation/
│           └── orchestration/
│
├── scripts/                          # bootstrap and helper scripts
├── templates/                        # DAG, dbt, Dockerfile starters
├── test_data/                        # CSV fixtures (HDR/TRL envelope pattern)
└── gcp-pipeline-libraries/           # LEGACY — predecessor Python framework (being retired)
    ├── gcp-pipeline-core
    ├── gcp-pipeline-beam
    ├── gcp-pipeline-orchestration
    ├── gcp-pipeline-transform
    ├── gcp-pipeline-tester
    └── gcp-pipeline-framework        # earlier internal iteration — being removed
```

## A note on the legacy tree

The `gcp-pipeline-libraries/` subtree is the predecessor framework — `groupId`-style package names beginning `gcp_pipeline_*`. It is retired in place: the code still exists as origin evidence but is not under active development. The v1 book manuscript's directory map (lines 5307–5313 of `gcp-pipeline-book.md`) shows this tree as the primary structure; that was accurate for the predecessor and is superseded here. The current framework lives exclusively in `data-pipeline-libraries-java/` (Java) and `data-pipeline-libraries/` (Python).

## What the two-tree split means in practice

The Java reactor is a Maven multi-module build whose parent POM lives at `data-pipeline-libraries-java/pom.xml`. Each module is a separate Maven artefact under `groupId com.enrichmeai.culvert`. The thirteen modules map cleanly onto the contract families: core (contracts + records + ServiceLoader discovery), one module per GCP service, two cloud-skeleton modules (AWS S3, Azure Blob), orchestration, and three test-support modules.

The Python library set mirrors the same contract families as separate distributions (currently named `data-pipeline-*`, with `culvert` as the planned coordinated-release name on PyPI). The `data-pipeline-transform` module has no Java twin: dbt is SQL and macros and is therefore language-neutral by nature — one Python package serves both runtimes.

\newpage
