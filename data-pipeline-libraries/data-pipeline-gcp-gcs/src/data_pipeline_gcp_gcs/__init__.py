"""Google Cloud Storage adapter for the Culvert data pipeline framework.

Implements the cloud-neutral ``BlobStore`` Protocol from
``data-pipeline-core`` over ``google-cloud-storage``.
"""

from __future__ import annotations

from data_pipeline_gcp_gcs.blob_store import GcsBlobStore

__version__ = "0.1.0"

__all__ = ["GcsBlobStore"]
