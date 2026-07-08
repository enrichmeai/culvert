# Helm chart — reference-e2e-gcp

Thin wrapper over the shared **pipeline-beam-runner** chart. Carries only this
deployment's values.

```bash
helm dependency build deployments/reference-e2e-gcp/helm
helm lint deployments/reference-e2e-gcp/helm
```
