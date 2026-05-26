"""
Secret Manager Hook for Google Cloud
"""

import logging
from typing import Optional

try:
    from airflow.providers.google.cloud.hooks.base import CloudBaseHook
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    CloudBaseHook = object

try:
    from google.cloud import secretmanager
    SM_AVAILABLE = True
except ImportError:
    SM_AVAILABLE = False

logger = logging.getLogger(__name__)

class SecretManagerHook(CloudBaseHook if AIRFLOW_AVAILABLE else object):
    """
    Hook to fetch credentials from Google Cloud Secret Manager.

    Provides a unified way for both Airflow DAGs and Beam pipelines
    (when called from within a Beam worker or Composer environment)
    to access sensitive data.
    """

    def __init__(
        self,
        gcp_conn_id: str = "google_cloud_default",
        **kwargs
    ):
        if AIRFLOW_AVAILABLE:
            super().__init__(gcp_conn_id=gcp_conn_id, **kwargs)
        self.gcp_conn_id = gcp_conn_id
        self._client = None

    def get_client(self) -> 'secretmanager.SecretManagerServiceClient':
        """Get the Secret Manager client."""
        if not SM_AVAILABLE:
            raise ImportError(
                "google-cloud-secret-manager is required for SecretManagerHook. "
                "Install with: pip install google-cloud-secret-manager"
            )

        if not self._client:
            if AIRFLOW_AVAILABLE:
                self._client = secretmanager.SecretManagerServiceClient(
                    credentials=self.get_credentials()
                )
            else:
                self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get_secret(self, secret_id: str, project_id: Optional[str] = None, version_id: str = "latest") -> str:
        """
        Fetch secret value from Secret Manager.

        Args:
            secret_id: ID of the secret
            project_id: GCP project ID (optional, uses hook project if not provided)
            version_id: Secret version ID (default: 'latest')

        Returns:
            The secret value as a string
        """
        client = self.get_client()
        
        if not project_id:
            if AIRFLOW_AVAILABLE:
                project_id = self.project_id
            else:
                raise ValueError("project_id must be provided if Airflow is not available")

        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        
        return payload
