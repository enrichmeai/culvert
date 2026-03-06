# Airflow GKE Deployment

This directory contains the custom Airflow Docker image and Helm values for deploying Airflow on GKE.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GKE Cluster                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                 Airflow Namespace                             │  │
│  │                                                               │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐  │  │
│  │  │  Webserver  │   │  Scheduler  │   │  Worker Pods        │  │  │
│  │  │             │   │             │   │  (KubernetesExec)   │  │  │
│  │  └─────────────┘   └─────────────┘   └─────────────────────┘  │  │
│  │         │                 │                    │              │  │
│  │         └─────────────────┼────────────────────┘              │  │
│  │                           │                                   │  │
│  │              ┌────────────▼────────────┐                      │  │
│  │              │  Custom Airflow Image   │                      │  │
│  │              │  (this Dockerfile)      │                      │  │
│  │              │  - gcp-pipeline-core    │                      │  │
│  │              │  - gcp-pipeline-orch    │                      │  │
│  │              └─────────────────────────┘                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│                         ▲ DAGs synced from GCS                      │
└─────────────────────────┼───────────────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │  gs://<project>-      │
              │  airflow-dags/        │
              │  - ingestion_dag.py   │
              │  - transform_dag.py   │
              │  - ...                │
              └───────────────────────┘
```

## Docker Images

| Image | Purpose | Location |
|-------|---------|----------|
| **airflow-custom** | Airflow runtime with libraries | `infrastructure/k8s/airflow/Dockerfile` |
| **dag-validator** | CI/CD DAG syntax validation | `deployments/data-pipeline-orchestrator/Dockerfile` |

### Why Two Dockerfiles?

1. **`infrastructure/k8s/airflow/Dockerfile`** (Airflow Runtime)
   - This is the actual Airflow image deployed on GKE
   - Contains `gcp-pipeline-core` and `gcp-pipeline-orchestration`
   - DAGs are NOT baked in - they sync from GCS at runtime
   - Built and pushed to GCR: `gcr.io/<project>/airflow-custom:latest`

2. **`deployments/data-pipeline-orchestrator/Dockerfile`** (Validation Only)
   - Used for CI/CD to validate DAG syntax before deployment
   - Does NOT run Airflow in production
   - Just verifies DAGs can be imported without errors

## Files

| File | Description |
|------|-------------|
| `Dockerfile` | Custom Airflow image with pipeline libraries |
| `values.yaml` | Helm values for production deployment |
| `values-simple.yaml` | Simplified Helm values for testing |

## Build & Deploy

```bash
# Build custom image
cd infrastructure/k8s/airflow
gcloud builds submit --tag gcr.io/<PROJECT_ID>/airflow-custom:latest .

# Deploy with Helm
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --create-namespace \
  --version 1.11.0 \
  --values values.yaml

# Sync DAGs
gsutil -m rsync -r deployments/data-pipeline-orchestrator/dags/ gs://<PROJECT_ID>-airflow-dags/
```

## Access Airflow UI

```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow

# Open http://localhost:8080
# Default credentials: admin / admin
```

