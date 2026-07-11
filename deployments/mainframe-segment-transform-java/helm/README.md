# Helm chart — mainframe-segment-transform-java

Thin wrapper over the shared **pipeline-beam-runner** chart. Carries only this
deployment's values.

```bash
helm dependency build deployments/mainframe-segment-transform-java/helm
helm lint deployments/mainframe-segment-transform-java/helm
```
