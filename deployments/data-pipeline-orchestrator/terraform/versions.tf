# Per-deployment Terraform root for data-pipeline-orchestrator.
# Owns the orchestrator runner service account and — ONLY when enable_composer
# is true — a Cloud Composer environment. Per docs/framework-evolution/
# 14-execution-tiers.md the demo (Tier 3a) runs enable_composer=false: no
# Composer is provisioned, so no standing cost; orchestration is Cloud Scheduler
# -> Cloud Run or local Airflow. Composer is stood up only for the deliberate
# Tier-3b pre-publish validation window, then torn down.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "gcs" {
    prefix = "deployments/data-pipeline-orchestrator"
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
