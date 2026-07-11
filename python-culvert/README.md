# Culvert

**A cloud-agnostic, polyglot data-pipeline framework.** One contract set —
`Source`, `Sink`, `Transform`, `Pipeline`, `RuntimeContext`, `BlobStore`,
`Warehouse`, `JobControlRepository`, and friends — realised in **Java and
Python**, with cloud specifics behind adapters. Define the pipeline once
against contracts; point it at an emulator on your laptop, a dev project, or
production by wiring, not rewriting.

- **Contract-driven** — the [language-neutral spec](https://github.com/enrichmeai/culvert/blob/main/docs/CONTRACT.md)
  is the portability boundary. Business logic depends only on contracts.
- **Two clouds today** — GCP is the first full implementation; AWS is a real
  (Java) adapter family with the same pipeline proven on both. Azure is on the
  roadmap.
- **No application framework in the core** — plain Python Protocols +
  entry-point auto-discovery; composes into Beam pipelines, Airflow DAGs, or a
  script on your laptop.
- **Local-first** — the whole stack runs against emulators with zero cloud
  account; cloud is where you prove and ship, not where you develop.

## Install

```bash
pip install culvert                 # core contracts only (no cloud SDKs)
pip install culvert[gcp]            # + BigQuery, GCS, Pub/Sub, Secret Manager, observability
pip install culvert[orchestration]  # + Airflow-side DAG factory, operators, sensors
pip install culvert[transform]      # + dbt integration
pip install culvert[all]
```

Python ≥ 3.10. For 0.1.0 the import packages keep their library names — the
contracts live in `data_pipeline_core`:

```python
from data_pipeline_core import autoconfig

config = autoconfig.discover()          # entry-point adapter discovery
blob_store = config.blob_store()        # GcsBlobStore if culvert[gcp] installed
```

The Java twin ships as `com.enrichmeai.culvert:*` on Maven Central — same
contracts, Java owns the Beam/Dataflow execution layer; Python owns the
Airflow runtime and dbt packaging.

## Status

`0.1.0` — first public release. Built and validated against a real GCP
project (Cloud Run, BigQuery, Pub/Sub, event-driven end-to-end) before
publishing. GCP adapters are production-shaped; the AWS family is Java-side;
Azure is a roadmap skeleton. Honest limitations are documented per adapter in
the source.

Docs, architecture, worked example deployments, and the engineering story:
**https://github.com/enrichmeai/culvert**

MIT licensed.
