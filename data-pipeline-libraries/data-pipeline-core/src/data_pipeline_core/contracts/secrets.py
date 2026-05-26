"""SecretProvider — single seam for secret lookup.

Existing GCP-adjacent shape: `gcp_pipeline_orchestration.hooks.secrets`
provides a Secret Manager hook with `get_secret(secret_id, project_id,
version_id)`. Stage 2 will adapt the method names: `get_secret` ->
`get`, `secret_id` -> `name`, `version_id` -> `version`, and lift the
class out of the orchestration package into `data-pipeline-gcp-secrets`.

The default cloud-neutral implementation is `EnvSecretProvider` (added
in Stage 3), which reads from environment variables.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """Look up secrets by name. Implementations call Secret Manager,
    AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or just
    read from the environment.
    """

    def get(self, name: str, version: str = "latest") -> str:
        """Return the secret value at `name` (and optional `version`).

        Raises KeyError if the secret does not exist. Implementations
        should never log the returned value, even at DEBUG level.
        """
        ...
