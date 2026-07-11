# Helm chart — fdp-to-consumable-product

Thin wrapper over the shared **pipeline-dbt-runner** chart
(`infrastructure/k8s/charts/pipeline-dbt-runner`, a scheduled dbt CronJob). Carries
only this deployment's values.

```bash
helm dependency build deployments/fdp-to-consumable-product/helm
helm lint  deployments/fdp-to-consumable-product/helm
```
