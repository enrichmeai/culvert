# Per-deployment Terraform root for bigquery-to-mapped-product (dbt).
# Owns only this deployment's own resources: the dbt runner service account +
# least-privilege IAM on the source/target datasets. The datasets themselves
# (odp_generic, fdp_generic, stg_generic) are shared substrate provisioned by
# infrastructure/terraform/systems/generic/transformation and injected as vars.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "gcs" {
    prefix = "deployments/bigquery-to-mapped-product"
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
