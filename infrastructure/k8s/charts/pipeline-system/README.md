# pipeline-system Helm Chart

The umbrella chart that deploys the complete GCP data pipeline system, including Airflow orchestration, dbt transformations, Apache Flink for beam pipelines, and full observability stack (OTEL, Prometheus, Grafana).

## Prerequisites

Install Helm 3.x and ensure kubectl is configured for your GKE cluster.

Optional: For pipeline-beam-runner, install the Flink Kubernetes Operator:

```bash
helm repo add flink-operator https://archive.apache.org/dist/flink/flink-kubernetes-operator-1.19.0/
helm install flink-operator flink-operator/flink-kubernetes-operator \
  --namespace flink-operator \
  --create-namespace
```

## Quick Start

First, update Helm dependencies:

```bash
cd infrastructure/k8s/charts/pipeline-system
helm dependency update
```

Deploy with default values:

```bash
helm install pipeline . \
  --namespace pipeline \
  --create-namespace
```

Or use a values file:

```bash
helm install pipeline . \
  --namespace pipeline \
  --create-namespace \
  --values values-simple.yaml
```

For production:

```bash
helm install pipeline . \
  --namespace pipeline \
  --create-namespace \
  --values values-prod.yaml
```

## Subcharts

| Chart | Purpose | Enabled by default |
|-------|---------|-------------------|
| `pipeline-airflow` | DAG orchestration via Apache Airflow | Yes |
| `pipeline-dbt-runner` | Scheduled dbt transformations | Yes |
| `pipeline-beam-runner` | Apache Flink for Beam pipelines | No |
| `pipeline-observability` | OTEL, Prometheus, Grafana | Yes |

Disable subcharts by setting `enabled: false` in values:

```yaml
pipeline-beam-runner:
  enabled: false
```

## Configuration

### Global Values

```yaml
global:
  system_id: "gcp-pipeline"
  environment: "dev"
  image_pull_secrets: []
```

### Key Overrides

Override per-subchart settings using the subchart name as the key:

```yaml
pipeline-dbt-runner:
  gcs:
    targetProject: my-project
  dbt:
    target: prod

pipeline-observability:
  prometheus:
    retention: "30d"
```

## Accessing Services

**Airflow UI:**
```bash
kubectl port-forward svc/airflow-webserver 8080:8080 -n pipeline
# http://localhost:8080
```

**Grafana:**
```bash
kubectl port-forward svc/pipeline-observability-grafana 3000:3000 -n pipeline
# http://localhost:3000 (admin / admin)
```

## Cleanup

```bash
helm uninstall pipeline -n pipeline
```

To also delete persistent data:

```bash
kubectl delete pvc --all -n pipeline
```
