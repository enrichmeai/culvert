# Culvert

> A cloud-neutral, polyglot data-pipeline framework. One contract, two languages (Java + Python), with Google Cloud as the first implementation.

Culvert is a framework for building data pipelines that are **defined once against a language-neutral contract and implemented in the language that fits the job**. The same 16 contracts (Source, Sink, Transform, Pipeline, RuntimeContext, BlobStore, Warehouse, FinOpsSink, GovernancePolicy, …) are realised in both a Java library set and a Python library set; cloud specifics live behind adapters, so the core stays portable across clouds.

> **Status — in progress.** The Java reactor has reached its v1.0 feature bar (all 16 contract interfaces have real adapters) and is **frozen at tag `java-0.1.0`**. It is **built and held, not yet published**: the release gate is **Java _and_ Python both ready**, then a single coordinated `0.1.0` to Maven Central (`com.enrichmeai.culvert:*`) and PyPI (`culvert`). Python parity is underway — contracts, core depth, and the GCP adapters have landed; `culvert` packaging and publish-from-git remain. **Nothing is on Maven Central or PyPI yet.** Authoritative plan: [`docs/framework-evolution/13-python-parity-release.md`](docs/framework-evolution/13-python-parity-release.md).

> **Repo vs product.** The GitHub repo is `enrichmeai/culvert`; the working-tree folder is still `gcp-pipeline-reference`. The folder name is an operational identifier, not the product name.

---

## Why Culvert

- **Contract-driven.** [`docs/CONTRACT.md`](docs/CONTRACT.md) is the language-neutral specification. Any team can implement it in any language; Java and Python are the two reference implementations.
- **Cloud-neutral by design.** The core depends only on contracts. GCP is the first full implementation; AWS is now a real (Java) adapter family — `BlobStore` (S3), `SecretProvider` (Secrets Manager), `Source`/`Sink` (SQS), and a transactional `JobControlRepository` (DynamoDB), with `Warehouse` (Athena) and observability hooks (CloudWatch) in progress. Azure Blob remains a single-method adapter skeleton.
- **Polyglot, not duplicated.** The two languages do not do the same job — see the division of labour below.
- **No application framework in the core.** Plain Java (JDK 17, `ServiceLoader` auto-config) and plain Python (Protocols + entry-point auto-config), so the libraries compose into Beam pipelines, Airflow DAGs, or anything else without dragging in Spring/Quarkus.

## Division of labour

| Layer | Strategy | Notes |
|---|---|---|
| **Contracts** | **Both** implement the same spec | 16 interfaces + the `StageMetrics` record. Java in `data-pipeline-core-java`; Python Protocols in `data-pipeline-core`. |
| **dbt / transform** | **Reuse** (language-neutral) | dbt is SQL + macros — packaged in `data-pipeline-transform`; there is deliberately no Java transform module. |
| **Dataflow / execution** | **Java** (Apache Beam) | `data-pipeline-gcp-dataflow-java`. Legacy Python Beam is not carried forward. |
| **Orchestration** | **Reuse** — complementary | Python owns the Airflow runtime side; Java owns the cloud-neutral DAG model + renderers (`DagSpec`/`TaskSpec`, Airflow/Composer). |

## Repository layout

```
data-pipeline-libraries-java/   # Java reactor — Maven, groupId com.enrichmeai.culvert (18 modules)
  data-pipeline-core-java          # contracts + records + AutoConfig (ServiceLoader)
  data-pipeline-gcp-{bigquery,gcs,pubsub,secrets,observability,dataflow}-java
  data-pipeline-aws-{s3,secrets,sqs,dynamodb}-java   # real AWS adapter family (BlobStore, SecretProvider, Source/Sink, JobControlRepository)
  data-pipeline-aws-{athena,cloudwatch}-java         # in progress (Warehouse, observability hooks)
  data-pipeline-azure-blob-java                      # cloud-neutrality skeleton (BlobStore, exists() only)
  data-pipeline-orchestration-java             # DagSpec/TaskSpec + Airflow/Composer renderers
  data-pipeline-{contract-tests,tester,it-support}-java

data-pipeline-libraries/        # Python library set (distributions currently named data-pipeline-*)
  data-pipeline-core               # Protocols + records + AutoConfig (entry-points)
  data-pipeline-gcp-{bigquery,gcs,pubsub,secrets,observability}
  data-pipeline-{orchestration,transform,tester,contract-tests}

deployments/                    # reference example pipelines built on the framework
docs/                           # documentation (see index below)
docs/framework-evolution/       # canonical "why / what / when" for the redesign + sprints
```

> The legacy Python trees (`gcp-pipeline-libraries/`, the `gcp_pipeline_*` egg-info) belong to the predecessor framework and are being retired — see [Legacy](#legacy).

## Build & test

**Java** (JDK 17; the Maven toolchain is provisioned automatically):

```bash
mvn -f data-pipeline-libraries-java/pom.xml install        # build + unit tests, all modules
mvn -f data-pipeline-libraries-java/pom.xml -P it verify   # integration tests (Testcontainers; needs Docker)
```

**Python** (each package is an independent distribution — install editable, then run pytest):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e data-pipeline-libraries/data-pipeline-core pytest
pip install -e data-pipeline-libraries/data-pipeline-gcp-bigquery   # plus whichever adapters you need
pytest data-pipeline-libraries/data-pipeline-core/tests
```

Adapters self-register with the core — Python via entry-points under the `data_pipeline_core.adapters` group, Java via `ServiceLoader` — so `AutoConfig.discover()` finds every installed implementation.

## Contracts

The 16 contract interfaces are the heart of the framework. Read [`docs/CONTRACT.md`](docs/CONTRACT.md) for the language-neutral spec, and `data-pipeline-core-java/.../contracts/` (Java) or `data-pipeline-core/.../contracts/` (Python) for the implementations. Conformance is enforced by shared test suites (`data-pipeline-contract-tests*`) that every adapter binds to.

## Status & roadmap

The framework is being completed in sprint waves; the authoritative plan is [`docs/framework-evolution/13-python-parity-release.md`](docs/framework-evolution/13-python-parity-release.md).

- ✅ **Java reactor 0.1.0** — all 16 contracts have adapters; frozen at `java-0.1.0`.
- ✅ **Python contracts + core depth** — Protocols reconciled to Java; `DefaultRuntimeContext`, data-quality, governance policies, FinOps cost model.
- ✅ **Python GCP adapters** — secrets, observability, and per-service cost trackers; all auto-discoverable.
- 🟡 **AWS adapter family (Sprint 21, epic #144)** — `S3BlobStore` (all 8 `BlobStore` methods), `AwsSecretsManagerProvider`, `SqsSource`/`SqsSink`, and a transactional `DynamoDbJobControlRepository` (conditional writes closing a real gap in BigQuery's job-control story) are done, unit- and LocalStack-IT-tested. Athena (`Warehouse`) and CloudWatch observability hooks are in progress. Out of scope for this block: an AWS execution layer (Beam is runner-portable; EMR/Flink is a future runner story) and AWS parity on the Python side. Azure remains a `BlobStore`-only skeleton.
- ⏳ **Packaging & coordinated release** — `culvert` PyPI distribution + publish-from-git, then a single `0.1.0` to Maven Central **and** PyPI.

Architecture: [`docs/framework-evolution/10-architecture.md`](docs/framework-evolution/10-architecture.md). Full series (audit, redesign, dev process, sprint plans): [`docs/framework-evolution/`](docs/framework-evolution/).

## Legacy

Culvert replaces the predecessor PyPI framework `gcp-pipeline-framework` (last release `1.0.29`). That package is being **deprecated in place** — left installable for existing pins, with a final pointer release to Culvert — **not** deleted. Do not build new work against it.

## Documentation index

- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the language-neutral contract spec.
- [`docs/framework-evolution/`](docs/framework-evolution/) — canonical why/what/when (redesign rationale, dev process, sprint plans, parity/release plan).
- Topic guides: [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md), [`docs/FINOPS_STRATEGY.md`](docs/FINOPS_STRATEGY.md), [`docs/DATA_QUALITY_GUIDE.md`](docs/DATA_QUALITY_GUIDE.md), [`docs/OBSERVABILITY_SPEC.md`](docs/OBSERVABILITY_SPEC.md).
- `deployments/*/` — worked example pipelines.

> Many guides under `docs/` were written for the predecessor reference implementation and are mid-migration; where they disagree with `docs/framework-evolution/`, the latter is current.

## License

MIT — see each module's `pom.xml` / `pyproject.toml`.
