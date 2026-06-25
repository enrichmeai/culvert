"""SecretManagerProvider — SecretProvider Protocol over Google Cloud Secret Manager.

Java sibling:
``com.enrichmeai.culvert.gcp.secrets.SecretManagerProvider``
(data-pipeline-libraries-java/data-pipeline-gcp-secrets-java/src/main/java/
com/enrichmeai/culvert/gcp/secrets/SecretManagerProvider.java).

Key shapes mirrored from Java (file:line references):
- ENV_PROJECT_ID = "GCP_PROJECT_ID"           (line 47)
- No-arg constructor reads GCP_PROJECT_ID env  (lines 61-63)
- (str, client) constructor for test injection  (lines 86-89)
- get(name, version="latest") resolves          (lines 92-108)
  projects/{projectId}/secrets/{name}/versions/{version}
- NotFoundException → KeyError (Python) / NoSuchElementException (Java line 106)
- close() delegates to underlying client        (lines 112-113)
- Never log the secret payload (documented invariant)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

ENV_PROJECT_ID = "GCP_PROJECT_ID"

_SENTINEL = object()  # distinguish "not provided" from explicit None


class SecretManagerProvider:
    """SecretProvider implementation backed by Google Cloud Secret Manager.

    Resolves secrets at::

        projects/{project_id}/secrets/{name}/versions/{version}

    Construction mirrors the Java sibling exactly:

    * **No-arg** — reads ``GCP_PROJECT_ID`` from the environment and builds a
      default ``SecretManagerServiceClient``.  Required for entry-point /
      ``AutoConfig.discover()`` instantiation.
    * **Two-arg (project_id, client)** — inject a mock client in unit tests.
      Mirrors Java ``SecretManagerProvider(String, SecretManagerServiceClient)``
      (lines 86-89). ``client`` must not be ``None``.

    Raises:
        KeyError: if the secret does not exist (mirrors Java ``NoSuchElementException``).
        TypeError: if ``name`` or ``client`` is ``None``.
        ValueError: if ``project_id`` is empty.
    """

    def __init__(self, project_id: str | None = None, client: Any = _SENTINEL) -> None:
        """
        Args:
            project_id: GCP project ID.  If *None*, reads ``GCP_PROJECT_ID``
                from the environment (mirrors Java no-arg constructor, line 61).
            client: Pre-built ``SecretManagerServiceClient``.  If omitted, a
                default client is created via Application Default Credentials.
                Passing ``None`` explicitly raises ``TypeError`` — mirrors Java
                ``Objects.requireNonNull(client)`` (line 88).
        """
        if project_id is None:
            project_id = self._require_env_project_id()
        if not project_id:
            raise ValueError("project_id must not be empty")
        self.project_id = project_id

        if client is _SENTINEL:
            # No client supplied — build a default one.
            client = self._create_default_client()
        if client is None:
            raise TypeError("client must not be None")
        self.client = client

    # --- SecretProvider Protocol ------------------------------------------

    def get(self, name: str, version: str = "latest") -> str:
        """Return the secret value at *name* (and optional *version*).

        Mirrors Java ``get(String name, String version)`` (lines 92-108).

        Raises:
            TypeError: if ``name`` is ``None``.
            KeyError: if the secret or version does not exist.
        """
        if name is None:
            raise TypeError("name must not be None")
        if version is None:
            raise TypeError("version must not be None")

        secret_version_path = (
            f"projects/{self.project_id}/secrets/{name}/versions/{version}"
        )
        try:
            response = self.client.access_secret_version(
                request={"name": secret_version_path}
            )
            # Never log the returned payload — documented invariant.
            return response.payload.data.decode("utf-8")
        except Exception as exc:
            if self._is_not_found(exc):
                raise KeyError(
                    f"Secret not found: projects/{self.project_id}"
                    f"/secrets/{name}/versions/{version}"
                ) from exc
            raise

    def close(self) -> None:
        """Close the underlying client. Mirrors Java ``close()`` (line 112)."""
        if hasattr(self.client, "close"):
            self.client.close()

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _require_env_project_id() -> str:
        """Read GCP_PROJECT_ID from the environment.

        Mirrors Java ``requireEnvProjectId()`` (lines 116-126).
        """
        value = os.environ.get(ENV_PROJECT_ID, "")
        if not value:
            raise EnvironmentError(
                f"Environment variable {ENV_PROJECT_ID} is not set; "
                "required for the no-arg constructor (entry-point discovery). "
                f"Either set {ENV_PROJECT_ID} or pass project_id explicitly."
            )
        return value

    @staticmethod
    def _create_default_client() -> Any:
        """Build a default SecretManagerServiceClient.

        Mirrors Java ``createDefaultClient()`` (lines 129-135).
        Wraps the import so tests that mock the client bypass the SDK entirely.
        """
        try:
            from google.cloud import secretmanager  # type: ignore[import]

            return secretmanager.SecretManagerServiceClient()
        except Exception as exc:
            raise RuntimeError(
                "Failed to create SecretManagerServiceClient; "
                "ensure google-cloud-secret-manager is installed and "
                "Application Default Credentials are configured."
            ) from exc

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        """Duck-type not-found detection across SDK versions.

        The google-cloud SDK raises ``google.api_core.exceptions.NotFound``
        (code 404); duck-type rather than import to stay loosely coupled.
        """
        code = getattr(exc, "code", None)
        if code == 404:
            return True
        grpc_code = getattr(exc, "grpc_status_code", None)
        if grpc_code is not None and str(grpc_code) in ("StatusCode.NOT_FOUND", "5"):
            return True
        msg = str(exc).lower()
        return "not found" in msg or "404" in msg
