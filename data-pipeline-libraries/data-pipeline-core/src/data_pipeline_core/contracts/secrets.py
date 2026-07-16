"""SecretProvider — single seam for secret lookup.

The GCP implementation is `SecretManagerProvider` in
`data-pipeline-gcp-secrets` (`get(name, version)` against Secret
Manager); the AWS twin is `AwsSecretsManagerProvider` on the Java side.

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
