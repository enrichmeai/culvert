# Per-deployment Terraform root for mainframe-segment-transform-java.
# Owns ONLY this deployment's own resources (runner SA + IAM + Tier-3a Cloud Run
# job). Shared substrate (buckets/topics/datasets) is injected as variables per
# docs/framework-evolution/15-per-deployment-iac.md, never re-created here.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "gcs" {
    prefix = "deployments/mainframe-segment-transform-java"
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
