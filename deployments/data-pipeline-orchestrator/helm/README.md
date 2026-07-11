# Helm chart — data-pipeline-orchestrator

Thin wrapper over the shared **pipeline-airflow** chart
(`infrastructure/k8s/airflow`, Airflow on Kubernetes). This is the
Composer-alternative orchestration path: it runs the same `culvert_dags.py`
(built from `config/system.yaml` via `DagFactory`) on self-hosted Airflow, so
the demo incurs no Cloud Composer cost. See
`docs/framework-evolution/14-execution-tiers.md`.

```bash
helm dependency build deployments/data-pipeline-orchestrator/helm
helm lint  deployments/data-pipeline-orchestrator/helm
```
