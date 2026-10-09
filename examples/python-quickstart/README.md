# Python quickstart: GCS to BigQuery in 14 lines

`ingest.py` reads JSON-lines orders from Cloud Storage. It keeps the paid ones, hashes their
emails, and loads them into a BigQuery table.

## 1. Install

```bash
pip install "culvert[gcp]"
```

> **Needs the next release.** `run`, `BlobLinesSource` and `BigQueryTableSink` are on `main`, not in
> `culvert` 0.4.0 on PyPI. Until the next release, install from a checkout of this repository:
> `pip install "./python-culvert[gcp]"`.

That one extra brings what this example needs:

- the core (`run`, `BlobLinesSource`, the decorators);
- the GCS and BigQuery adapters;
- the Google client libraries.

There is no separate starter package to keep in step.

## 2. Sign in

```bash
gcloud auth application-default login
```

The clients use Application Default Credentials.

- **Your account needs:**
  - read access to the bucket;
  - `bigquery.jobs.create` and write access to the dataset, for example
    `roles/bigquery.dataEditor` on the dataset plus `roles/bigquery.jobUser` on the project.
- **The project:** BigQuery bills the project named in the table. Use `project.dataset.table`, or
  `dataset.table` for the default project.

## 3. Run it

```bash
python ingest.py gs://my-bucket/orders/2026-10-09.jsonl my-project.sales.orders
# 3 read, 2 loaded into my-project.sales.orders
```

- **The dataset must exist.** The table is created on the first load.
- **Pass a schema for a real table.** Without one, BigQuery detects a schema from the first batch
  (the first 10 000 records), and every later batch must fit it. A field that is empty in that
  batch, or an integer that later turns into a string, fails the run partway. Pass a schema:

  ```python
  from google.cloud import bigquery

  BigQueryTableSink(table, schema=[
      bigquery.SchemaField("id", "INT64"),
      bigquery.SchemaField("status", "STRING"),
      bigquery.SchemaField("email", "STRING"),
  ])
  ```

## What each piece does

| Piece | What it does |
|---|---|
| `BlobLinesSource(uri, store, format="jsonl")` | Reads one or more objects as records: JSON lines (one object per line) or CSV (a header row). It works with any `BlobStore` (GCS, S3, in-memory). |
| `@transform()` | Names the function as a stage. |
| `@masked(fields=[...], policy="hash")` | Masks fields of the records the stage returns. The policy is one of `full`, `partial`, `redacted`, `hash` or `none`. `"hash"` uses a fixed default salt, so common values can be guessed back. For real privacy, pass `policy=MaskingPolicy(MaskingStrategy.HASH, salt=<your secret>)`. |
| `run(source, transforms, sink)` | Streams the records through the stages in order, in this process. It returns the counts read and written. |
| `BigQueryTableSink(table)` | Writes with BigQuery load jobs of up to 10 000 records each. Each job is all or nothing and is waited on, and a failure raises. |

**When things go wrong:**

- **Partial loads.** A load job that fails raises, and the run stops. Earlier batches stay loaded,
  so re-run with `write_disposition="WRITE_TRUNCATE"` or de-duplicate downstream.
- **Values JSON cannot carry are refused** before their batch is sent, naming the field: NaN or
  infinity, bytes, sets. So are malformed lines, and CSV rows with more fields than the header.
- **Empty input sends nothing.** A truncating write with no records leaves the table as it was.
- **Large files are streamed.** A GCS object is read in chunks, pinned to the version that was
  there when the read began; an object replaced mid-read fails the run rather than mixing versions.
- **Byte-order marks are dropped.** Files that start with one, as Excel and Windows tools write,
  read correctly.

**What `run` does not do:**

- **No retries.** It does not retry, and it swallows nothing; it is a plain loop.
- **No scheduling or scale-out.** That is the orchestrator's job: Airflow, with the DAG factory in
  `culvert[orchestration]`.

**Adding more:**

- **`@quality_check(schema, min_score=0.99)`** holds back records that fail the schema, and raises
  when too many fail.
- **`@governed("project.dataset.table")`** reports the table and its governance as a lineage
  event.

## Tested

`data-pipeline-libraries/data-pipeline-gcp-bigquery/tests/test_quickstart_example.py` runs this file
end to end, with the GCS and BigQuery clients replaced by fakes. It also checks the file stays
within 20 lines of code.
