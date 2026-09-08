# data-pipeline-gcp-bigquery (Python)

Google Cloud BigQuery adapter for the Culvert data pipeline framework. Implements the cloud-neutral [`Warehouse`](../data-pipeline-core/src/data_pipeline_core/contracts/warehouse.py) and [`FinOpsSink`](../data-pipeline-core/src/data_pipeline_core/contracts/finops.py) Protocols from `data-pipeline-core`, plus the **write path** of [`JobControlRepository`](../data-pipeline-core/src/data_pipeline_core/contracts/job_control.py).

**Java sibling:** `com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse` in `data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/`. Same contract; same behaviour.

## Install

```bash
pip install data-pipeline-gcp-bigquery
```

Pulls in `data-pipeline-core` and `google-cloud-bigquery`.

## Usage

```python
from google.cloud import bigquery
from data_pipeline_gcp_bigquery import BigQueryWarehouse

client = bigquery.Client(project="my-project")
warehouse = BigQueryWarehouse("my-project", client)

for row in warehouse.query("SELECT id, name FROM dataset.customers"):
    print(row)
```

## Contract methods

| Method | Behaviour |
|---|---|
| `query(sql, params=None)` | Lazy iterator of result dicts |
| `execute(sql, params=None)` | DML/DDL; result discarded |
| `load_from_uri(uri, target_table, schema, options)` | Bulk-load GCS URI with an explicit `LoadOptions` write disposition; returns rows loaded |
| `merge(source_table, target_table, keys)` | Raises `NotImplementedError` — sprint-4 scope |
| `copy(source_table, target_table)` | Returns target's post-copy row count |
| `table_exists(fqtn)` | True/False, no exception on 404 |

## `BigQueryJobControlRepository`

The Python write path for `job_control.pipeline_jobs`. Spine AD-14 rule 1: *no
code writes `job_control.*` except through `JobControlRepository`*. Before this
class existed the Python side had no implementation of that port at all, so two
deployments hand-rolled their own DML; both now call this.

```python
from data_pipeline_core.job_control_api import JobStatus, PipelineJob
from data_pipeline_gcp_bigquery import BigQueryJobControlRepository

repo = BigQueryJobControlRepository(project_id="my-project")   # job_control.pipeline_jobs
repo.create_job(PipelineJob(run_id=..., status=JobStatus.RUNNING, ...))
repo.update_status(run_id, JobStatus.SUCCEEDED, total_records=1234)
```

| Method | Behaviour |
|---|---|
| `create_job(job)` | Parameterised DML `INSERT` of the authoritative 23-column shape; writes `job.status`, not a hard-coded `created` |
| `update_status(run_id, status, total_records=None)` | Stamps `started_at` on `running`, `completed_at` on a terminal status |
| `mark_failed(run_id, error_code, error_message, failure_stage, error_file_path=None)` | Records structured error context and closes the run out |

Every statement is a DML query job, never `insert_rows_json` — a streamed row
sits in BigQuery's streaming buffer and is invisible to the terminal `UPDATE`
for up to ~30 minutes. Every statement also checks `num_dml_affected_rows` and
raises `JobControlWriteError` if it moved no row (spine AD-5: a job-control
write must never fail silently).

**Scope:** write path only. The Python reads live in
`data_pipeline_orchestration._job_control` and move to the projection in
migration-plan Phase 3; the full eleven-method surface is in the Java sibling
`BigQueryJobControlRepository.java`.

## Testing

```bash
cd data-pipeline-libraries/data-pipeline-gcp-bigquery
pip install -e ".[test]"
pytest
```

All tests pass with `unittest.mock` — no real GCP required.

## Sprint-3 deliverable

Issue [#12](https://github.com/enrichmeai/culvert/issues/12) (Python Stage 2 epic). Mirrors the sprint-1 Java module.
