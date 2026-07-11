# 15 — Per-deployment IaC: terraform/ + helm/ in every deployment

**Status:** convention (decided 2026-07). Every active deployment under
`deployments/` carries its own `terraform/` root and `helm/` chart, so a
deployment is a **self-contained, independently deployable unit** — you can
`cd` into it and stand up exactly what it needs, nothing more.

## The rule

```
deployments/<name>/
  terraform/            # this deployment's OWN GCP resources (thin root)
    versions.tf         #   provider + partial GCS backend
    variables.tf        #   inputs, incl. shared-substrate refs + toggles
    main.tf             #   runner SA + IAM + target table/dataset + Tier-3a Cloud Run job
    outputs.tf
    terraform.tfvars.example
  helm/                 # wrapper chart over the matching central runtime chart
    Chart.yaml          #   dependency: pipeline-beam-runner | pipeline-dbt-runner
    values.yaml         #   deployment-specific overrides only
    templates/NOTES.txt
    README.md
```

## Two hard constraints (why this isn't copy-paste)

1. **Terraform owns only what's unique to the deployment.** The shared substrate
   — landing/archive/error buckets, the file-notification Pub/Sub topic, the ODP
   datasets — is provisioned once by the system-level Terraform
   (`infrastructure/terraform/systems/generic/*`). A deployment's `terraform/`
   takes those as **variables** and creates only its own resources (runner
   service account + least-privilege IAM, the target table it loads, and — when
   `enable_cloud_run_job=true` — the Tier-3a Cloud Run executor). Re-creating the
   shared substrate per deployment would collide across the ingestion pipelines.

2. **Helm wraps, never forks.** The runner logic lives in the central charts
   (`infrastructure/k8s/charts/pipeline-beam-runner` for Flink-on-GKE beam jobs;
   `pipeline-dbt-runner` for dbt CronJobs). A deployment's `helm/` is an umbrella
   chart that declares the central chart as a `file://` dependency and supplies
   only its own values. All beam deployments move in lockstep because they share
   one runner template.

## Runtime → central chart map

| Deployment kind | Deployments | Helm wraps | Terraform provisions |
|---|---|---|---|
| Java/Beam | original-data-to-bigqueryload-java, postgres-cdc-streaming-java, mainframe-segment-transform-java, reference-e2e-gcp | `pipeline-beam-runner` | runner SA, target table, Tier-3a Cloud Run job |
| dbt | bigquery-to-mapped-product, fdp-to-consumable-product, spanner-to-bigquery-load | `pipeline-dbt-runner` | runner SA, target dataset IAM, CronJob schedule vars |
| Airflow DAGs | data-pipeline-orchestrator | `pipeline-system` | orchestration (Composer **optional**, `enable_composer=false` default → Cloud Scheduler → Cloud Run) |
| Cloud Run trigger | fdp-trigger | `pipeline-system` (GKE alt) | Cloud Run service + invoker IAM |

The three retired Python deployments (`original-data-to-bigqueryload`,
`postgres-cdc-streaming`, `mainframe-segment-transform`) do **not** get IaC —
they are superseded by their `-java` counterparts.

## Execution paths are chosen, not forked

A beam deployment can run three ways off the *same* artifact — the choice is a
flag/var, never a code or chart fork (see
[14 — execution tiers](14-execution-tiers.md)):

- **GKE / Flink** — apply the deployment's `helm/` chart.
- **Cloud Run (Tier 3a demo)** — `terraform/` with `enable_cloud_run_job=true`.
- **Dataflow (Tier 3b prod)** — launch the jar with `--runner=DataflowRunner`.

## Verification (per deployment, part of DoD)

```bash
terraform -chdir=deployments/<name>/terraform fmt -check
terraform -chdir=deployments/<name>/terraform init -backend=false && terraform -chdir=... validate
helm dependency build deployments/<name>/helm && helm lint deployments/<name>/helm
```
