# Chapter 3 — GCP Fundamentals, Zero to Hero

This chapter is the on-ramp. If you have never built a data pipeline on Google Cloud, read it carefully. If you have, skim it for the conventions — and the vocabulary — the rest of this book assumes. Either way, read the final section, because the point of this chapter is not to teach you GCP. It is to show you *why Culvert's first full implementation lives there*, and to name every GCP service that sits behind an adapter before we start opening those adapters up in Part III.

## The concrete first cloud

Every framework has to start somewhere. Culvert started on GCP.

That was not an arbitrary call. The team had built three production pipeline deployments on Google Cloud before writing a line of framework code. We had opinions forged in the middle of the night when a Dataflow job drained off the end of a watermark and nobody's alert fired. We knew which knobs mattered and which were dials stuck at their factory settings. We knew that the 30-line "hello Beam" example in every Google tutorial conceals roughly eight weeks of production work — quarantine handling, reconciliation, audit trails, IAM segregation, cost tracking, dead-letter routing — and we were tired of rewriting that same eight weeks for each new pipeline.

The framework came out of that frustration. The GCP implementation is the *real* one: all 16 contract interfaces have living adapter classes; the Java reactor has been frozen at `java-0.1.0` with the full adapter set in place (`README.md`). When Part III walks you through the adapter modules — `data-pipeline-gcp-gcs-java`, `data-pipeline-gcp-pubsub-java`, `data-pipeline-gcp-bigquery-java`, `data-pipeline-gcp-dataflow-java`, `data-pipeline-gcp-secrets-java`, `data-pipeline-gcp-observability-java` — this chapter is the map you will want to have already read.

So: GCP fundamentals. One mental model. The core services in one paragraph each. A handful of minimal examples that demonstrate not what the framework does but what it *saves you from*. Then forward into the rest of the book.

## The mental model

A data pipeline on GCP, at the most reductive level, is a four-stage object:

```
[ Source ] → [ Land ] → [ Process ] → [ Serve ]
```

- **Source** is wherever the data is born — a mainframe extract, a Postgres database, a third-party SaaS export, a Kafka topic.
- **Land** is where it first arrives in the platform — almost always Cloud Storage.
- **Process** is the work of validating, transforming, joining, and shaping it — Dataflow, dbt, BigQuery scheduled queries.
- **Serve** is wherever consumers reach in — BigQuery for analysts, Looker for dashboards, Pub/Sub for downstream systems.

Every service we will discuss occupies one of those boxes. Once you have the boxes in mind, the services stop feeling like a confusing menu and start feeling like a small set of choices *per box*. Culvert's contracts map directly onto these stages: `Source` and `Sink` contracts govern data entry and exit; `Warehouse` governs the serve layer; `Pipeline` and `PipelineStage` govern the processing graph. The GCP adapters are the implementations that wire those contracts to the real services. The mapping is not accidental.

## The core services in one paragraph each

**Cloud Storage (GCS).**\index{Cloud Storage} Object storage. Buckets contain objects; objects have keys; everything is HTTP under the hood. Storage classes (Standard, Nearline, Coldline, Archive) trade cost against retrieval latency. Lifecycle rules\index{Cloud Storage!lifecycle rules} move objects between classes automatically. Notifications\index{Cloud Storage!notifications} let GCS publish to Pub/Sub when an object lands — that event is usually the starting gun for a Culvert pipeline run. The unit of work is the object, not the file system. The adapter is `GcsBlobStore`, which implements the `BlobStore` contract (`data-pipeline-gcp-gcs-java`, `GcsBlobStore.java:1–49`); chapters 7 and 8 cover it in full.

**Pub/Sub.**\index{Pub/Sub} Managed publish/subscribe messaging. Publishers push messages to a topic\index{Pub/Sub!topics}; subscribers pull — or get pushed — from a subscription\index{Pub/Sub!subscriptions}. At-least-once delivery by default; exactly-once is available with a configuration flip. Acknowledgements are required, retries are automatic, dead-letter\index{Pub/Sub!dead letter} routing is built in. Pub/Sub is the GCP equivalent of Kafka for most use cases — simpler, less tunable, and almost always good enough. The Culvert adapters are `PubSubSource` (implementing `Source`) and `PubSubSink` (implementing `Sink`) in `data-pipeline-gcp-pubsub-java`; chapter 7 covers both. Note the at-most-once trade-off baked into `PubSubSource.read()`: messages are acknowledged before the iterator is returned to the caller (`PubSubSource.java:24–27`). That is a deliberate contract-level decision — callers needing at-least-once must wire a separate subscriber.

**Dataflow.**\index{Dataflow} Managed runner for Apache Beam\index{Apache Beam} pipelines. You write a Beam program in Java; Dataflow takes it, autoscales\index{Dataflow!autoscaling} the worker pool, and runs it as either a batch or a streaming job. Beam's programming model is map/reduce/group with side inputs and side outputs; it parallelises naturally; it handles late-arriving data with watermarks. Culvert's adapter is `DataflowPipeline`, which implements the `Pipeline` contract and bridges it to Beam's `DataflowRunner` (`data-pipeline-gcp-dataflow-java`, `DataflowPipeline.java:29–56`). The contract is intentionally scheduler-agnostic — it describes the DAG, not how stages execute. Chapter 9 is dedicated to this adapter.

**BigQuery.**\index{BigQuery} A serverless analytics warehouse. You create datasets\index{BigQuery!datasets}; datasets contain tables; tables can be partitioned\index{BigQuery!partitioning} and clustered. Storage is columnar and compressed. Queries scan data and bill on bytes scanned (on-demand) or slot-seconds\index{BigQuery!slots} (flat rate). BigQuery is unique among warehouses in that there is no cluster to manage; you cannot oversize or undersize it. The Culvert adapter is `BigQueryWarehouse`, which implements the `Warehouse` contract and issues all operations as BigQuery jobs (`data-pipeline-gcp-bigquery-java`, `BigQueryWarehouse.java:35–48`). Chapter 8 covers the warehouse, job control, and the FinOps sink that writes cost metrics back into BigQuery itself.

**Cloud Composer.**\index{Cloud Composer} Managed Apache Airflow\index{Airflow} on GKE. You write DAGs in Python; Composer schedules, runs, monitors, and retries them. Cloud Composer 2 starts at roughly 300 USD per month before you schedule a single task.\index{Cloud Composer!cost} Use it when you genuinely need Airflow; use Cloud Functions or Cloud Run Jobs when you do not.\index{Cloud Composer!alternatives} Culvert's orchestration module (`data-pipeline-orchestration-java`) provides a cloud-neutral DAG model — `DagSpec` and `TaskSpec` — with a Composer renderer that emits Python DAG files. The Python side owns the Airflow runtime itself. Chapter 11 covers the full orchestration story.

**Secret Manager.**\index{Secret Manager} Managed secret storage — API keys, database passwords, service-account credentials. Secrets are versioned; access is logged; rotation is first-class. The Culvert adapter is `SecretManagerProvider`, which implements the `SecretProvider` contract and resolves secrets at `projects/{projectId}/secrets/{name}/versions/{version}` (`data-pipeline-gcp-secrets-java`, `SecretManagerProvider.java:1–40`). The no-arg constructor reads `GCP_PROJECT_ID` from the environment and registers via `ServiceLoader`, so `AutoConfig.discover()` finds it automatically. Secrets never touch logs — not at DEBUG, not ever.

**Cloud Trace and Cloud Monitoring.**\index{Cloud Trace}\index{Cloud Monitoring} Tracing and metrics. Cloud Trace stores distributed spans; Cloud Monitoring stores time-series metrics and drives alert policies. Culvert's adapter is `CloudTraceObservabilityHook`, which implements the `ObservabilityHook` contract and bridges to OpenTelemetry — whose `SdkTracerProvider` is wired to the GCP exporter by the caller (`data-pipeline-gcp-observability-java`, `CloudTraceObservabilityHook.java:19–40`). The design is deliberately decoupled: the hook does not know it is talking to GCP; the OTel exporter configuration does. `CloudMonitoringMetricsHook` provides the metrics side. Chapter 12 covers observability and lineage in full.

That is, modulo a few specialised services we will meet in passing (Cloud Data Catalog for lineage, Cloud KMS for customer-managed encryption, Workload Identity Federation for keyless CI authentication), the entire GCP substrate this book uses.

## The simplest possible GCP pipeline, in 30 lines

To make all of the above concrete, here is the smallest pipeline that does something useful: read a CSV from GCS, count the rows, write the count to BigQuery.

```python
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

class CountToRow(beam.DoFn):
    def process(self, element):
        yield {"file_uri": "gs://example/in.csv", "row_count": element}

def run():
    options = PipelineOptions(
        runner="DataflowRunner",
        project="my-project",
        region="europe-west2",
        temp_location="gs://example/tmp",
        staging_location="gs://example/staging",
    )

    with beam.Pipeline(options=options) as p:
        (
            p
            | "Read"      >> beam.io.ReadFromText("gs://example/in.csv", skip_header_lines=1)
            | "ToOnes"    >> beam.Map(lambda _: 1)
            | "Sum"       >> beam.CombineGlobally(sum)
            | "ToRow"     >> beam.ParDo(CountToRow())
            | "WriteBQ"   >> beam.io.WriteToBigQuery(
                "my-project:example.row_counts",
                schema="file_uri:STRING,row_count:INTEGER",
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

if __name__ == "__main__":
    run()
```

That is a complete, runnable pipeline. It is also a useless one in production: there is no schema validation, no error handling, no audit trail, no cost tracking, no reconciliation, no `run_id`. None of those are optional extras. Every pipeline that handles real data, real volumes, and real downstream consumers needs all of them. The gap between this 30-line example and a production-ready Beam job is eight weeks of work the first time you close it. It is the work Culvert was built to carry for you.

## The simplest possible orchestration, in 20 lines

A trivially small Airflow DAG that runs the above:

```python
from airflow import DAG
from airflow.providers.google.cloud.operators.dataflow import DataflowCreatePythonJobOperator
from datetime import datetime

with DAG(
    dag_id="example_count",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:
    DataflowCreatePythonJobOperator(
        task_id="count_rows",
        py_file="gs://example/code/count.py",
        job_name="example-count-{{ ds_nodash }}",
        location="europe-west2",
        options={"runner": "DataflowRunner"},
    )
```

Complete, runnable, and missing every important production property. No retry policy. No SLA. No alerting. No dependency on upstream landing. No audit. No idempotence. Culvert's orchestration module (`data-pipeline-orchestration-java`) provides all of those by composition — you define a `DagSpec` once, and the Composer renderer emits a Python DAG with them included.

## The simplest possible transformation, in 10 lines

A minimal dbt model:

```sql
-- models/example/row_counts_daily.sql
{{ config(materialized='table') }}

SELECT
    DATE(load_ts) AS load_date,
    SUM(row_count) AS total_rows
FROM {{ source('example', 'row_counts') }}
GROUP BY 1
```

Useful, simple, and missing audit columns, PII masking, incremental materialisation, and tests. dbt is the one component in Culvert that is genuinely language-neutral — SQL plus macros — and the framework does not wrap it: `data-pipeline-transform` packages the dbt project directly, with no Java or Python translation layer on top. Chapter 10 covers the reasoning.

## The hidden complexity of the simple version

If you ran the three snippets above in sequence, you would have a "pipeline" that:

- Has no encryption at rest or in transit beyond what GCP applies by default.
- Has no IAM segregation (every service runs as your user credentials).
- Has no dead-letter handling (a bad row silently drops the message).
- Has no observability beyond stdout and whatever Dataflow logs to Cloud Logging by default.
- Has no testing harness — you cannot run a unit test against any part of it.
- Has no concept of who triggered what when, or what the source row count was, or whether the BigQuery row count agrees with it.
- Costs roughly the same as the production version because it leaves Composer and Pub/Sub running whether they have work to do or not.

Every line of Culvert exists to close one of those gaps. The `GcsBlobStore` exists because object stores without lifecycle rules and uniform-bucket-level access quietly become compliance problems. The `SecretManagerProvider` exists because hardcoding credentials is not a shortcut — it is a debt that compounds. The `CloudTraceObservabilityHook` exists because "observe it in stdout" is not observability. As we walk through the adapter modules in Part III, recognise that what looks like complexity is, in almost every case, *load-bearing* complexity — there because the simple version was wrong in production.

The framework does not make pipelines simpler. It makes the right amount of complexity easier to carry.

## Culvert's GCP adapter map

Before we leave this chapter, here is a one-table reference that maps the six GCP adapter modules to the contracts they implement and the chapters that cover them in detail. You will want this when the later chapters refer back to module names.

| Module | Key classes | Contract(s) | Chapter |
|---|---|---|---|
| `data-pipeline-gcp-gcs-java` | `GcsBlobStore`, `QuarantineHandler`, `GcsCostTracker` | `BlobStore`, `FinOpsSink` | 7, 13 |
| `data-pipeline-gcp-pubsub-java` | `PubSubSource`, `PubSubSink`, `PubSubCostTracker` | `Source`, `Sink`, `FinOpsSink` | 7, 13 |
| `data-pipeline-gcp-bigquery-java` | `BigQueryWarehouse`, `BigQueryFinOpsSink`, `BigQueryAuditEventPublisher` | `Warehouse`, `FinOpsSink` | 8, 13 |
| `data-pipeline-gcp-dataflow-java` | `DataflowPipeline` | `Pipeline` | 9 |
| `data-pipeline-gcp-secrets-java` | `SecretManagerProvider` | `SecretProvider` | (cross-cutting) |
| `data-pipeline-gcp-observability-java` | `CloudTraceObservabilityHook`, `CloudMonitoringMetricsHook`, `DataCatalogLineageEmitter` | `ObservabilityHook` | 12 |

All six modules are in the Java reactor under `data-pipeline-libraries-java/` (`README.md:31–37`). Equivalent Python adapters live under `data-pipeline-libraries/data-pipeline-gcp-{gcs,pubsub,bigquery,secrets,observability}/` and implement the same contracts via Python Protocols.

## A glossary refresher

A few terms you will see throughout the book, defined once here:\index{ODP}\index{FDP}\index{CDP}\index{run\_id}\index{HDR/TRL}\index{quarantine}\index{reconciliation}

- **ODP** — Original Data Product. The untransformed BigQuery layer that mirrors source extracts.
- **FDP** — Foundation Data Product. The clean, business-shaped layer.
- **CDP** — Consumable Data Product. Narrow, contracted views derived from FDP.
- **Run ID** — A unique identifier per pipeline execution, threaded through every artefact: the GCS object key, the BigQuery audit row, the Pub/Sub message attribute, the Cloud Trace span.
- **HDR/TRL** — Header/Trailer envelope on a mainframe extract file. The envelope row-count claim is what reconciliation checks against.
- **Quarantine** — The four-stage workflow (REVIEW, HOLD, DELETE, ARCHIVE) for rejects and intentional deletions. `QuarantineHandler` in `data-pipeline-gcp-gcs-java` is the implementation.
- **Reconciliation** — The check that envelope count, valid count, invalid count, and BigQuery row count all agree. A pipeline that does not reconcile cannot be trusted.

## What zero to hero looks like

By the end of this book you will be able to:

- Take an unfamiliar data source and design a Culvert-backed ingestion pipeline for it in an afternoon.
- Add a new entity to a running framework deployment in less than a working day, by implementing the contracts and letting `AutoConfig.discover()` wire it in.
- Diagnose a failed run end-to-end using only the audit trail, the run ID, and Cloud Trace.
- Justify, with numbers, the choice between Composer and Cloud Functions for orchestration.
- Read a `DagSpec` and understand what the Composer renderer will produce from it.
- Know which six adapter modules to look in when something goes wrong on GCP.

That is hero. The GCP fundamentals in this chapter are the ground beneath it. The contracts in Part II are the frame. The adapters in Part III are what makes the frame load-bearing.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Every GCP pipeline is a four-stage object: Source → Land → Process → Serve. Culvert's contract set maps directly onto those stages; the six GCP adapter modules are what make the mapping real.
  \item The 30-line Beam example is complete and runnable. It is also missing reconciliation, audit, cost tracking, PII masking, retries, dead-letter handling, and IAM segregation. Each of those gaps is load-bearing in production — and closing them is what Culvert was built to carry.
  \item The six GCP adapter modules — \texttt{data-pipeline-gcp-\{gcs,pubsub,bigquery,dataflow,secrets,observability\}-java} — are all present and frozen at \texttt{java-0.1.0}. Nothing is published yet; the release gate is Java and Python both ready, then a single coordinated \texttt{0.1.0} to Maven Central and PyPI.
  \item \texttt{ODP}, \texttt{FDP}, \texttt{CDP}, \texttt{run\_id}, \texttt{HDR/TRL}, \texttt{quarantine}, and \texttt{reconciliation} are framework vocabulary used throughout the book; they are defined once here.
\end{itemize}
\end{takeaways}

\newpage
