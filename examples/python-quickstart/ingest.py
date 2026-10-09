"""Culvert quickstart: JSON-lines orders in GCS -> paid only, emails hashed -> BigQuery.

    pip install "culvert[gcp]"
    python ingest.py gs://my-bucket/orders/2026-10-09.jsonl my-project.sales.orders
"""
import sys

from google.cloud import storage

from data_pipeline_core import BlobLinesSource, masked, run, transform
from data_pipeline_gcp_bigquery import BigQueryTableSink
from data_pipeline_gcp_gcs import GcsBlobStore


@transform()
@masked(fields=["email"], policy="hash")
def paid_orders(records, context):
    return (r for r in records if r.get("status") == "paid")


if __name__ == "__main__":
    uri, table = sys.argv[1], sys.argv[2]
    source = BlobLinesSource(uri, GcsBlobStore(storage.Client()))
    result = run(source, [paid_orders], BigQueryTableSink(table))
    print(f"{result.records_read} read, {result.records_written} loaded into {table}")
