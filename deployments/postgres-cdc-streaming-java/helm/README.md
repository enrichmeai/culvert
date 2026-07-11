# Helm chart — postgres-cdc-streaming-java

Thin wrapper over the shared **pipeline-beam-runner** chart. Carries only this
deployment's values.

```bash
helm dependency build deployments/postgres-cdc-streaming-java/helm
helm lint deployments/postgres-cdc-streaming-java/helm
```
