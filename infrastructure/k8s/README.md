# Kubernetes Infrastructure

This directory contains Kubernetes manifests for deploying **Airflow orchestrator on GKE**.

> **Note**: Ingestion runs on **Dataflow** and transformation runs on **BigQuery** - both are Google-managed services, NOT containers on GKE.

## Architecture

```
GKE Cluster
└── airflow namespace
    ├── Scheduler (Pod)
    ├── Webserver (Pod)
    └── Workers (Pods) - for task execution
    
Triggered Services (NOT on GKE):
├── Dataflow - Beam ingestion pipelines
└── BigQuery - dbt transformations
```

## Structure

```
k8s/
├── README.md
├── airflow/           # Airflow Helm values
│   └── values.yaml    # Configuration for apache-airflow chart
└── workloads/         # Service accounts for Workload Identity
    ├── namespace.yaml
    └── serviceaccount.yaml
```

## Quick Start

```bash
# 1. Create namespace
kubectl apply -f k8s/workloads/namespace.yaml

# 2. Create service accounts (replace PROJECT_ID first)
sed "s/PROJECT_ID/${PROJECT_ID}/g" k8s/workloads/serviceaccount.yaml | kubectl apply -f -

# 3. Install Airflow using Helm
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --values k8s/airflow/values.yaml
```

## See Also

- [GKE_DEPLOYMENT_GUIDE.md](../../docs/GKE_DEPLOYMENT_GUIDE.md) - Full deployment guide

