# Helm chart — original-data-to-bigqueryload

Thin wrapper over the shared **pipeline-beam-runner** chart
(`infrastructure/k8s/charts/pipeline-beam-runner`, Flink Kubernetes Operator).
It carries only this deployment's values; the runner templates stay central so
every beam deployment stays in lockstep.

```bash
helm dependency build deployments/original-data-to-bigqueryload-java/helm
helm lint  deployments/original-data-to-bigqueryload-java/helm
helm template ingestion deployments/original-data-to-bigqueryload-java/helm \
  --set pipeline-beam-runner.gcs.bucket=my-demo-temp \
  --set pipeline-beam-runner.serviceAccount.gcpSaEmail=$(terraform -chdir=../terraform output -raw runner_service_account)
```

Execution paths (pick one; see `docs/framework-evolution/14-execution-tiers.md`):
- **GKE / Flink** — this chart.
- **Cloud Run (Tier 3a demo)** — `terraform/` `enable_cloud_run_job=true`.
- **Dataflow (Tier 3b prod)** — launch the jar with `--runner=DataflowRunner`.
