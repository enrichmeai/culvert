# Helm chart — spanner-to-bigquery-load

Thin wrapper over the shared **pipeline-dbt-runner** chart. Reads Spanner through
a BigQuery external connection (see `../terraform`).

```bash
helm dependency build deployments/spanner-to-bigquery-load/helm
helm lint deployments/spanner-to-bigquery-load/helm
```
