# Per-deployment Terraform root for spanner-to-bigquery-load (dbt).
# The dbt project (spanner_transformation) reads Spanner through a BigQuery
# EXTERNAL CONNECTION (dbt_project.yml: spanner_connection_id), not direct
# Spanner access — so the runner SA needs bigquery.connectionUser on that
# connection, NOT spanner.databaseReader (the connection carries its own Spanner
# identity). Target dataset (fdp_spanner) is shared substrate injected as a var.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "gcs" {
    prefix = "deployments/spanner-to-bigquery-load"
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
