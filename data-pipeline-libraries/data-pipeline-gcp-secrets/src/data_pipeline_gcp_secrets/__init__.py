"""Google Cloud Secret Manager adapter for the Culvert data pipeline framework.

Implements the cloud-neutral ``SecretProvider`` Protocol from
``data-pipeline-core`` over ``google-cloud-secret-manager``.
"""

from __future__ import annotations

from data_pipeline_gcp_secrets.secret_manager_provider import SecretManagerProvider

__version__ = "0.1.0"

__all__ = ["SecretManagerProvider"]
