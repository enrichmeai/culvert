# GKE Deployment Guide — Alternative Orchestration Pattern

> **Culvert deployment guide.** The reference deployments live under `deployments/`:
> Java Dataflow pipelines (`original-data-to-bigqueryload-java`,
> `postgres-cdc-streaming-java`, `mainframe-segment-transform-java`,
> `reference-e2e-gcp`), dbt transforms (`bigquery-to-mapped-product`,
> `fdp-to-consumable-product`, `spanner-to-bigquery-load`), and the config-driven
> orchestrator (`data-pipeline-orchestrator`, built on the `data-pipeline-orchestration`
> library — no more `generate_dags.py` codegen). The GCP steps here are Culvert's
> **first-implementation** operations; the deploy→test→validate→publish gate is in
> [`docs/framework-evolution/13-python-parity-release.md`](framework-evolution/13-python-parity-release.md) §2.
> Predecessor `gcp-pipeline-framework` names in older passages are superseded — the
> framework is **Culvert** ([`README.md`](../README.md)). Nothing is on PyPI/Maven Central yet.

> **Pattern:** Alternative | **Primary pattern:** [Cloud Composer (deploy-generic.yml)](../. github/workflows/deploy-generic.yml)

This guide demonstrates deploying the **same three-unit Generic pipeline** using **GKE-hosted Airflow** as the orchestration runtime instead of Cloud Composer. The Dataflow ingestion and dbt transformation units are identical between both patterns — only the orchestration runtime differs.

| Component | This Pattern (GKE) | Primary Pattern (Cloud Composer) |
|-----------|-------------------|----------------------------------|
| **Orchestration (Airflow)** | GKE — self-managed Helm | Cloud Composer — fully managed |
| **Ingestion (Beam)** | Dataflow (Google-managed) | Dataflow (Google-managed) |
| **Transformation (dbt)** | BigQuery (Google-managed) | BigQuery (Google-managed) |
| **Library** | `gcp-pipeline-framework==1.0.11` | `gcp-pipeline-framework==1.0.11` |
| **CI/CD Workflow** | `deploy-gke.yml` | `deploy-generic.yml` |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GKE CLUSTER                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AIRFLOW (Orchestration Only)                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │  Scheduler  │  │  Webserver  │  │   Workers   │                  │   │
│  │  │   (Pod)     │  │   (Pod)     │  │   (Pods)    │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  │                           │                                          │   │
│  │                           ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │              DAGs (synced from GCS)                          │    │   │
│  │  │  • pubsub_trigger_dag.py  → Triggers Dataflow                │    │   │
│  │  │  • odp_load_dag.py        → Runs Dataflow jobs               │    │   │
│  │  │  • fdp_transform_dag.py   → Runs dbt on BigQuery             │    │   │
│  │  │  • error_handling_dag.py  → Monitors job_control             │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ Triggers via Operators
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐
│         DATAFLOW              │  │         BIGQUERY              │
│   (Google Managed)            │  │    (Google Managed)           │
│  ┌─────────────────────────┐  │  │  ┌─────────────────────────┐  │
│  │  Beam Ingestion Jobs    │  │  │  │  dbt Transformations    │  │
│  │  • Parse CSV            │  │  │  │  • Staging models       │  │
│  │  • Validate records     │  │  │  │  • FDP models           │  │
│  │  • Load to ODP          │  │  │  │  • Data quality tests   │  │
│  └─────────────────────────┘  │  │  └─────────────────────────┘  │
└───────────────────────────────┘  └───────────────────────────────┘
```

## When to Use Each Pattern

| Aspect | Cloud Composer (Primary) | Airflow on GKE (Alternative) |
|--------|--------------------------|------------------------------|
| **Cost** | ~£300-500/month minimum | ~£50-100/month |
| **Operational overhead** | Minimal — Google-managed | Higher — team manages Helm, upgrades |
| **Customisation** | Limited plugin/package control | Full control over Airflow config |
| **Multi-tenancy** | One Composer env per project | Multiple namespaces on one cluster |
| **Scaling** | Managed auto-scaling | Custom HPA/VPA configuration |
| **Recommended for** | Most enterprise teams | Cost-sensitive or highly customised setups |

**Why Dataflow and BigQuery remain the same in both patterns:**
- Dataflow auto-scales workers, handles retries natively, and is fully managed
- BigQuery executes dbt SQL directly — no compute to manage
- Running Beam/dbt in containers adds operational overhead with no benefit

---

## Prerequisites

### 1. GKE Cluster

```bash
# Create cluster
gcloud container clusters create pipeline-cluster \
  --zone europe-west2-a \
  --num-nodes 2 \
  --machine-type e2-standard-2 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 5 \
  --workload-pool=${PROJECT_ID}.svc.id.goog

# Get credentials
gcloud container clusters get-credentials pipeline-cluster --zone europe-west2-a
```

### 2. Service Account with Workload Identity

```bash
PROJECT_ID=$(gcloud config get-value project)

# Create GCP service account
gcloud iam service-accounts create airflow-sa \
  --display-name="Airflow Service Account"

# Grant permissions for Airflow to trigger Dataflow and BigQuery
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/dataflow.developer"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

# Bind to Kubernetes service account
gcloud iam service-accounts add-iam-policy-binding \
  airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[airflow/airflow-worker]"
```

### 3. GCS Bucket for DAGs

```bash
gsutil mb -l europe-west2 gs://${PROJECT_ID}-airflow-dags
```

---

## Part 1: Deploy Airflow on GKE

### Using Helm (Recommended)

```bash
# Add Helm repo
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Create namespace
kubectl create namespace airflow

# Install with custom values
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --values infrastructure/k8s/airflow/values.yaml
```

### Helm Values (infrastructure/k8s/airflow/values.yaml)

Key configurations:
- **KubernetesExecutor**: Dynamic pod creation for tasks
- **GCS DAG sync**: DAGs synced from `gs://${PROJECT_ID}-airflow-dags`
- **Workload Identity**: Service account for GCP access

See `infrastructure/k8s/airflow/values.yaml` for full configuration.

---

## Part 2: Deploy Dataflow Templates (Ingestion)

The DAGs use `DataflowStartFlexTemplateOperator` to trigger Beam pipelines on Dataflow.

### Build Flex Template

```bash
# Build and upload Flex Template
cd deployments/original-data-to-bigqueryload

gcloud dataflow flex-template build \
  gs://${PROJECT_ID}-dataflow-templates/templates/ingestion-pipeline.json \
  --image-gcr-path "gcr.io/${PROJECT_ID}/ingestion-pipeline:latest" \
  --sdk-language "PYTHON" \
  --flex-template-base-image "PYTHON3" \
  --metadata-file "metadata.json" \
  --py-path "src"
```

### DAG Usage (template_odp_load_dag.py)

```python
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator

run_dataflow = DataflowStartFlexTemplateOperator(
    task_id='run_dataflow_pipeline',
    project_id=PROJECT_ID,
    location=REGION,
    body={
        'launchParameter': {
            'jobName': f'{SYSTEM_ID_LOWER}-ingestion-{{{{ ds_nodash }}}}',
            'containerSpecGcsPath': f'gs://{PROJECT_ID}-dataflow-templates/templates/ingestion-pipeline.json',
            'parameters': {
                'source_file': '{{ dag_run.conf.file_metadata.data_file }}',
                'output_table': f'{PROJECT_ID}:odp_{SYSTEM_ID_LOWER}.{{{{ dag_run.conf.file_metadata.entity }}}}',
                'run_id': '{{ ti.xcom_pull(key="run_id") }}',
            },
        }
    },
)
```

---

## Part 3: Configure dbt for BigQuery (Transformation)

dbt runs SQL directly on BigQuery - no containers needed.

### Option A: BashOperator with dbt CLI

```python
from airflow.operators.bash import BashOperator

run_dbt = BashOperator(
    task_id='run_dbt_transform',
    bash_command=f'''
        cd /opt/airflow/dbt && \
        dbt run --select fdp.{SYSTEM_ID_LOWER} \
                --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' \
                --target prod
    ''',
)
```

### Option B: BigQueryInsertJobOperator (dbt compile → SQL)

```python
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

# Pre-compiled dbt SQL
run_transform = BigQueryInsertJobOperator(
    task_id='run_transform',
    configuration={
        'query': {
            'query': open('/opt/airflow/dbt/target/compiled/fdp_model.sql').read(),
            'useLegacySql': False,
        }
    },
)
```

### Option C: dbt Cloud Operator

```python
from airflow.providers.dbt.cloud.operators.dbt import DbtCloudRunJobOperator

run_dbt_cloud = DbtCloudRunJobOperator(
    task_id='run_dbt_cloud',
    job_id=12345,  # dbt Cloud job ID
    check_interval=30,
    timeout=3600,
)
```

---

## Part 4: Deployment Script

```bash
# Deploy everything
./scripts/gcp/deploy_to_gke.sh

# Deploy DAGs only (quick update)
./scripts/gcp/deploy_to_gke.sh --dags-only

# Deploy with Dataflow templates
./scripts/gcp/deploy_to_gke.sh --dataflow-templates
```

---

## Part 5: Verify Deployment

### 1. Access Airflow UI

```bash
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
# Open http://localhost:8080
```

### 2. Check DAGs

```bash
# List DAGs in GCS
gsutil ls gs://${PROJECT_ID}-airflow-dags/

# Check Airflow logs
kubectl logs -f deployment/airflow-scheduler -n airflow
```

### 3. Test End-to-End

```bash
# Upload test files to trigger pipeline (note: env suffix on bucket name)
gsutil cp test_customers_20260101.csv gs://${PROJECT_ID}-generic-int-landing/generic/customers/
gsutil cp customers.csv.ok gs://${PROJECT_ID}-generic-int-landing/generic/customers/

# Monitor in Airflow UI at http://localhost:8080
```

---

## Cost Comparison

| Component | Cloud Composer | GKE + Native Services |
|-----------|----------------|-----------------------|
| **Airflow** | ~$300-500/month | ~$50-100/month |
| **Ingestion** | (included) | Dataflow: pay per job |
| **Transformation** | (included) | BigQuery: pay per query |
| **Total (low usage)** | ~$400/month | ~$100/month |
| **Total (high usage)** | ~$1000+/month | ~$200-300/month |

---

## Troubleshooting

### DAGs not appearing in Airflow

```bash
# Check GCS sync
kubectl logs -f deployment/airflow-scheduler -n airflow | grep gcs

# Manual sync
kubectl exec -it deployment/airflow-scheduler -n airflow -- \
  gsutil -m rsync -r gs://${PROJECT_ID}-airflow-dags /opt/airflow/dags
```

### Dataflow job fails

```bash
# Check Dataflow logs
gcloud dataflow jobs list --region europe-west2
gcloud dataflow jobs describe JOB_ID --region europe-west2
```

### dbt errors

```bash
# Check BigQuery logs
bq ls -j -a --max_results=10
```

---

## Related Documentation

| Guide | Description |
|-------|-------------|
| [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) | Infrastructure setup — shared between both orchestration patterns |
| [Technical Architecture](./TECHNICAL_ARCHITECTURE.md) | Overall architecture and design decisions |
| [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) | End-to-end pipeline flow (same for both patterns) |
| [`deploy-generic.yml`](../.github/workflows/deploy-generic.yml) | Primary pattern — Cloud Composer CI/CD |
| [`deploy-gke.yml`](../.github/workflows/deploy-gke.yml) | This pattern — GKE CI/CD |

