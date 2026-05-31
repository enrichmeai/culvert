# data-pipeline-gcp-bigquery (Python)

Google Cloud BigQuery adapter for the Culvert data pipeline framework. Implements the cloud-neutral [`Warehouse`](../data-pipeline-core/src/data_pipeline_core/contracts/warehouse.py) Protocol from `data-pipeline-core`.

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
| `load_from_uri(uri, target_table, schema)` | Bulk-load GCS URI; returns rows loaded |
| `merge(source_table, target_table, keys)` | Raises `NotImplementedError` — sprint-4 scope |
| `copy(source_table, target_table)` | Returns target's post-copy row count |
| `table_exists(fqtn)` | True/False, no exception on 404 |

## Testing

```bash
cd data-pipeline-libraries/data-pipeline-gcp-bigquery
pip install -e ".[test]"
pytest
```

10 tests pass with `unittest.mock` — no real GCP required.

## Sprint-3 deliverable

Issue [#12](https://github.com/enrichmeai/culvert/issues/12) (Python Stage 2 epic). Mirrors the sprint-1 Java module.
