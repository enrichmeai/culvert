# data-pipeline-gcp-secrets (Python)

Google Cloud Secret Manager adapter for the Culvert data pipeline framework. Implements the cloud-neutral [`SecretProvider`](../data-pipeline-core/src/data_pipeline_core/contracts/secrets.py) Protocol.

**Java sibling:** `com.enrichmeai.culvert.gcp.secrets.SecretManagerProvider`
(`data-pipeline-libraries-java/data-pipeline-gcp-secrets-java/src/main/java/com/enrichmeai/culvert/gcp/secrets/SecretManagerProvider.java`).

## Install

```bash
pip install data-pipeline-gcp-secrets
```

## Usage

```python
from data_pipeline_gcp_secrets import SecretManagerProvider

# Production: reads GCP_PROJECT_ID from env, uses Application Default Credentials
provider = SecretManagerProvider()

# Explicit project:
provider = SecretManagerProvider("my-project-id")

value = provider.get("my-secret")           # latest version
value = provider.get("my-secret", "42")     # pinned version
```

## Environment variables

| Variable | Used by |
|---|---|
| `GCP_PROJECT_ID` | No-arg constructor (required for entry-point / AutoConfig discovery) |

## Errors

| Cause | Raised |
|---|---|
| Secret or version not found | `KeyError` |
| `name` is `None` | `TypeError` |
| Empty `project_id` | `ValueError` |
| `GCP_PROJECT_ID` unset (no-arg constructor) | `EnvironmentError` |
| Other Secret Manager errors | propagated |

## AutoConfig registration

This package registers itself under the `data_pipeline_core.adapters` entry-point group:

```toml
[project.entry-points."data_pipeline_core.adapters"]
secrets = "data_pipeline_gcp_secrets:SecretManagerProvider"
```

After `pip install -e .`, `AutoConfig.discover().secrets` will contain `SecretManagerProvider`.

## Testing

```bash
pip install -e ".[test]"
pytest
```

All tests run against a `unittest.mock.MagicMock` client — no real Secret Manager calls.

Sprint-19 deliverable (issue #124, T19.1 Wave C adapter parity).
