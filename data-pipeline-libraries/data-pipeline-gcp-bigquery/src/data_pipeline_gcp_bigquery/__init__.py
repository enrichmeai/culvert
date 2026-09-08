"""Google Cloud BigQuery adapter for the Culvert data pipeline framework.

Implements the cloud-neutral ``Warehouse``, ``FinOpsSink`` and (write-path)
``JobControlRepository`` Protocols from ``data-pipeline-core`` over
``google-cloud-bigquery``.
"""

from __future__ import annotations

from data_pipeline_gcp_bigquery.finops_sink import BigQueryFinOpsSink, FinOpsInsertException
from data_pipeline_gcp_bigquery.job_control import (
    BigQueryJobControlRepository,
    JobControlWriteError,
)
from data_pipeline_gcp_bigquery.warehouse import BigQueryWarehouse

__version__ = "0.1.0"

__all__ = [
    "BigQueryFinOpsSink",
    "BigQueryJobControlRepository",
    "BigQueryWarehouse",
    "FinOpsInsertException",
    "JobControlWriteError",
]
