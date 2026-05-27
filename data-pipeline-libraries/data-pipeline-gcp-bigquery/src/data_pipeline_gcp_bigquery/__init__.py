"""Google Cloud BigQuery adapter for the Culvert data pipeline framework.

Implements the cloud-neutral ``Warehouse`` Protocol from
``data-pipeline-core`` over ``google-cloud-bigquery``.
"""

from __future__ import annotations

from data_pipeline_gcp_bigquery.warehouse import BigQueryWarehouse

__version__ = "0.1.0"

__all__ = ["BigQueryWarehouse"]
