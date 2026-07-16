# pipeline-dbt-runner Helm Chart

A Helm chart for deploying dbt runners on Kubernetes. Provides both a scheduled CronJob for daily transformations and a Job template for on-demand execution via Airflow's KubernetesPodOperator.

## Building the image

The chart expects image `my-registry/pipeline-dbt-runner:1.7.14-0.1.1`. The `Dockerfile` in this directory builds it.

### Build locally

```bash
cd infrastructure/k8s/charts/pipeline-dbt-runner
make build
```

By default this produces `my-registry/pipeline-dbt-runner:1.7.14-0.1.1`.

### Build and push to your registry

```bash
make build push REGISTRY=gcr.io/your-project-id
```

Then update `values.yaml`:

```yaml
image:
  repository: gcr.io/your-project-id/pipeline-dbt-runner
  tag: "1.7.14-0.1.1"
```

### Override `culvert[transform]` source (private registry)

`culvert[transform]` is pulled from PyPI by default. To use a private Artifact Registry or Nexus index, pass `PIP_INDEX_URL` at build time:

```bash
make build \
  REGISTRY=gcr.io/your-project-id \
  PIP_INDEX_URL=https://us-python.pkg.dev/your-project/your-repo/simple/
```

The build arg is forwarded verbatim to `pip install --index-url`.

### Print version info

```bash
make version
```

### Local smoke test

```bash
# Authenticate first
gcloud auth application-default login

# Point at a real or stub dbt project
make run-local \
  LOCAL_PROJECT_DIR=/path/to/your/dbt-projects \
  LOCAL_PROFILES_DIR=/path/to/your/profiles

# Override target to 'dev' (already the default for run-local)
```

The `run-local` target runs `dbt debug` so you can verify connectivity without triggering a full model run.

### Volume mounts expected at runtime

| Mount path | Content | Required |
|---|---|---|
| `/app/projects/<DBT_PROJECT>/` | The dbt project directory (dbt_project.yml, models/, etc.) | Yes |
| `/app/profiles/profiles.yml` | dbt profiles file with BigQuery connection config | Yes |
| GCP credentials | Injected automatically by GKE Workload Identity — no key file needed in-cluster | No (WI handles it) |

**Workload Identity flow:** The Kubernetes ServiceAccount (`pipeline-dbt-runner`) is annotated with a GCP service account email (`serviceAccount.gcpSaEmail` in values.yaml). GKE injects a short-lived token into the pod via the metadata server, which dbt-bigquery's google-auth stack picks up automatically as Application Default Credentials.

**Environment variables** that control entrypoint behaviour:

| Variable | Default | Description |
|---|---|---|
| `DBT_PROJECT` | `bigquery-to-mapped-product` | Subdirectory under `/app/projects/` |
| `DBT_TARGET` | `prod` | dbt target from profiles.yml |
| `DBT_PROFILES_DIR` | `/app/profiles` | Path to directory containing profiles.yml |

## Install

```bash
helm install pipeline-dbt-runner ./pipeline-dbt-runner \
  --namespace pipeline \
  --create-namespace \
  --set gcs.targetProject=my-project \
  --set serviceAccount.gcpSaEmail=pipeline-dbt@my-project.iam.gserviceaccount.com
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `my-registry/pipeline-dbt-runner` | dbt runner image |
| `image.tag` | `1.7.14-0.1.1` | Image tag |
| `schedule.transformation` | `0 3 * * *` | CronJob schedule (3am daily) |
| `schedule.concurrencyPolicy` | `Forbid` | Prevent overlapping runs |
| `resources.requests.cpu` | `500m` | CPU request |
| `resources.limits.cpu` | `2000m` | CPU limit |
| `gcs.targetProject` | `` | GCP project ID (required) |
| `dbt.project` | `bigquery-to-mapped-product` | dbt project directory |
| `dbt.target` | `prod` | dbt target profile |
| `serviceAccount.gcpSaEmail` | `` | GCP service account for Workload Identity |

## Using with Airflow's KubernetesPodOperator

Reference the Job template ConfigMap in your DAG:

```python
from airflow.contrib.operators.kubernetes_pod_operator import KubernetesPodOperator

pod_operator = KubernetesPodOperator(
    task_id='dbt_run',
    pod_template_file='/path/to/job-template.yaml',
    namespace='pipeline',
)
```

Mount the ConfigMap containing the job template:

```bash
kubectl create configmap dbt-job-template \
  --from-file=job-template.yaml=./templates/job-template.yaml \
  -n pipeline
```

## Cleanup

```bash
helm uninstall pipeline-dbt-runner -n pipeline
```
