# 🚀 Creating a New Deployment Guide

This guide provides step-by-step instructions for creating a new migration pipeline deployment using the decoupled architecture of 4 functional libraries and 3 deployment units.

## 📋 Overview

The framework follows a **decoupled, library-first** approach. To create a new deployment for a system (e.g., `mysystem`), you create three independent deployment units that consume specialized libraries.

### 4 Specialized Libraries

1.  **`gcp-pipeline-core`**: Shared models (Audit, JobControl). No Beam/Airflow dependencies.
2.  **`gcp-pipeline-beam`**: Ingestion logic. Depends on `apache-beam`.
3.  **`gcp-pipeline-orchestration`**: Airflow sensors and DAG factories. Depends on `apache-airflow`.
4.  **`gcp-pipeline-transform`**: Shared dbt macros and SQL logic.

### 3 Independent Deployment Units

1.  **`mysystem-ingestion`**: Handles GCS → ODP load. Uses `gcp-pipeline-beam`.
2.  **`mysystem-transformation`**: Handles ODP → FDP transformation. Uses `gcp-pipeline-transform`.
3.  **`mysystem-orchestration`**: The "Conductor" (Airflow). Uses `gcp-pipeline-orchestration`.

---

## 🛠 Step-by-Step Instructions

### 1. Create the Deployment Structure

Create three independent folders under `deployments/` for your system.

```bash
mkdir -p deployments/mysystem-ingestion
mkdir -p deployments/mysystem-transformation
mkdir -p deployments/mysystem-orchestration
```

### 2. Set Up Ingestion Unit (`mysystem-ingestion`)

- **Define Beam Pipeline**: Create your Beam pipeline logic, extending `BasePipeline` from `gcp-pipeline-beam`.
- **Terraform**: Provision GCS landing buckets and ODP BigQuery datasets.
- **CI/CD**: Configure to build a Dataflow Flex Template image.

### 3. Set Up Transformation Unit (`mysystem-transformation`)

- **dbt Project**: Create a new dbt project for your system's transformations.
- **Shared Macros**: Reference `gcp-pipeline-transform` in your `packages.yml` or macro paths.
- **Terraform**: Provision FDP BigQuery datasets and dbt service accounts.

### 4. Set Up Orchestration Unit (`mysystem-orchestration`)

- **Initialize Folder**:
  ```bash
  mkdir -p deployments/mysystem-orchestration/dags
  ```
- **Copy Templates**: Use the standardized templates from the `templates/dags/` folder:
  ```bash
  cp templates/dags/template_*.py deployments/mysystem-orchestration/dags/
  ```
- **Rename & Customize**: Rename files to `mysystem_*.py` and follow the **Search and Replace** instructions in [DAG Development Guide](DAG_DEVELOPMENT_GUIDE.md).
- **Trigger Flow**: The templates come pre-configured with the standard 3-step flow (Trigger → ODP Load → FDP Transform).
- **Terraform**: Provision Cloud Composer and Pub/Sub topics.

### 5. Shared Audit and Core Logic

Ensure all units use the `gcp-pipeline-core` library for consistent auditing. This allows the Orchestration unit to start an audit record that the Ingestion and Transformation units can update.

---

## ✅ Checklist for Readiness

1. [ ] **System ID** is consistent across all three units.
2. [ ] **Ingestion Unit** successfully builds a Dataflow Flex Template.
3. [ ] **Transformation Unit** runs dbt models and passes data quality tests.
4. [ ] **Orchestration Unit** correctly senses .ok files and triggers the child units in order.
5. [ ] **Audit Trail** is consistent across all three units via the `core` library.

## 📚 Reference Implementations

- **[LOA Orchestration Example](../deployments/loa-orchestration/README.md)**: Split pattern (1 source → 2 targets).
- **[EM Orchestration Example](../deployments/em-orchestration/README.md)**: Join pattern (3 sources → 1 target).
