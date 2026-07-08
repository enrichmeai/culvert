# Helm chart — bigquery-to-mapped-product

Thin wrapper over the shared **pipeline-dbt-runner** chart
(`infrastructure/k8s/charts/pipeline-dbt-runner`, a scheduled dbt CronJob). Carries
only this deployment's values.

```bash
helm dependency build deployments/bigquery-to-mapped-product/helm
helm lint  deployments/bigquery-to-mapped-product/helm
```
