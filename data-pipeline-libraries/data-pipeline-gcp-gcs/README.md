# data-pipeline-gcp-gcs (Python)

Google Cloud Storage adapter for the Culvert data pipeline framework. Implements the cloud-neutral [`BlobStore`](../data-pipeline-core/src/data_pipeline_core/contracts/blob_store.py) Protocol.

**Java sibling:** `com.enrichmeai.culvert.gcp.gcs.GcsBlobStore`.

## Install

```bash
pip install data-pipeline-gcp-gcs
```

## Usage

```python
from google.cloud import storage
from data_pipeline_gcp_gcs import GcsBlobStore

client = storage.Client()
store = GcsBlobStore(client)

data = store.get("gs://my-bucket/path/to/file.json")
store.put("gs://my-bucket/output.json", b'{"ok": true}')
for uri in store.list("gs://my-bucket/dir/"):
    print(uri)
```

## URI scheme

Only `gs://bucket/path` URIs. Foreign schemes (`s3://`, `abfs://`) raise `ValueError`. Missing bucket or object path also raise `ValueError`.

## Errors

| Cause | Thrown |
|---|---|
| Missing object on `get`/`open` | `FileNotFoundError` |
| Missing object on `delete` | (silently swallowed — idempotent) |
| Non-`gs://` URI | `ValueError` |
| Other GCS errors | propagated |

## Testing

```bash
pip install -e ".[test]"
pytest
```

12 tests pass via `unittest.mock` — no real GCS.

Sprint-3 deliverable (issue #12 Python Stage 2 epic).
