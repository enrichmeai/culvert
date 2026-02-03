# Setting up Harness on GCP

This guide explains how to deploy a Harness Delegate on GCP to run your pipelines, even if you don't have an existing Harness infrastructure.

## 1. Prerequisites
- A GCP Project with Billing enabled.
- A Harness Account (you can sign up for a free trial at [harness.io](https://app.harness.io/auth/#/signup)).
- Your Harness **Account ID** and a **Delegate Token**.
  - Find these in Harness under: `Project Settings` -> `Delegates` -> `Tokens`.

## 2. Deploying the Harness Delegate on GCP

We provide a Terraform configuration to provision a Google Compute Engine (GCE) instance that runs the Harness Delegate as a Docker container.

### Step 2.1: Initialize Terraform
```bash
cd infrastructure/terraform/harness-delegate
terraform init
```

### Step 2.2: Apply Configuration
```bash
terraform apply \
  -var="project_id=YOUR_GCP_PROJECT_ID" \
  -var="harness_account_id=YOUR_HARNESS_ACCOUNT_ID" \
  -var="harness_delegate_token=YOUR_HARNESS_DELEGATE_TOKEN"
```

This will:
1. Create a dedicated VPC and Subnet.
2. Create a Service Account for the Delegate with `roles/editor` permissions (for testing).
3. Provision an `e2-medium` VM instance.
4. Install Docker and start the Harness Delegate container.

## 3. Connecting to GitHub

Once the Delegate is running and visible in your Harness Console:

1. **Create a GitHub Connector**:
   - Go to `Connectors` -> `New Connector` -> `GitHub`.
   - Use your GitHub personal access token.
   - Select "Connect through a Harness Delegate" and pick your new `gcp-delegate`.

2. **Import Pipelines**:
   - You can now create a new Pipeline in Harness and use the "Remote" option to point to the YAML files in your repository (e.g., `gcp-pipeline-libraries/harness-unified.yaml`).

## 4. Why host the Delegate on GCP?
- **Security**: The Delegate runs inside your GCP project, meaning you don't need to expose GCP keys to the Harness SaaS. The Delegate uses the VM's Service Account directly.
- **Performance**: Faster interactions with GCS, BigQuery, and Dataflow as the Delegate is co-located in the same GCP region.
- **Control**: You manage the lifecycle of the execution environment.
