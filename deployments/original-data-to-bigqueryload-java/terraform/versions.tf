# Per-deployment Terraform root for original-data-to-bigqueryload-java.
#
# Owns ONLY this deployment's own resources (runner service account + IAM, the
# ODP target table, and the Tier-3a Cloud Run executor job). The shared
# substrate — landing/archive/error buckets, the file-notification Pub/Sub
# topic — belongs to the system-level Terraform (infrastructure/terraform/
# systems/generic/ingestion) and is passed in as variables, not re-created here
# (re-creating it would collide with the other ingestion deployments).
#
# See docs/framework-evolution/14-execution-tiers.md: enable_cloud_run_job=true
# is the Tier-3a demo executor (Cloud Run, scale-to-zero). Dataflow (Tier-3b)
# is launched from the same jar via --runner=DataflowRunner and is not a
# standing resource, so it is not declared here.

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }

  # Partial backend: pass -backend-config=bucket=... at init, or run with
  # -backend=false for local validation. Mirrors the system-level backend.
  backend "gcs" {
    prefix = "deployments/original-data-to-bigqueryload-java"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
