# Segment Transform - Terraform Configuration
#
# Minimal infrastructure for the mainframe-segment-transform pipeline:
#   - GCS bucket (segment output files)
#   - BigQuery: cdp_generic.customer_risk_profile (partitioned on updated_at)
#   - BigQuery: job_control.pipeline_jobs + audit_trail
#
# Usage:
#   cd infrastructure/terraform/systems/segment
#   terraform init
#   terraform apply -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"
#   terraform destroy -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "gcp-pipeline-terraform-state"
    prefix = "segment"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# ============================================================================
# LOCAL VARIABLES
# ============================================================================

locals {
  project_id  = var.gcp_project_id
  region      = var.gcp_region
  environment = var.environment

  common_labels = {
    project     = "gcp-pipeline-reference"
    system      = "segment-transform"
    environment = local.environment
    managed_by  = "terraform"
  }
}

# ============================================================================
# GCS BUCKET — Segment output files
# ============================================================================

resource "google_storage_bucket" "segments" {
  name          = "${local.project_id}-generic-${local.environment}-segments"
  location      = local.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY — CDP dataset + customer_risk_profile table
# ============================================================================

resource "google_bigquery_dataset" "cdp" {
  dataset_id = "cdp_generic"
  location   = var.bq_location

  labels = local.common_labels
}

resource "google_bigquery_table" "customer_risk_profile" {
  dataset_id          = google_bigquery_dataset.cdp.dataset_id
  table_id            = "customer_risk_profile"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "updated_at"
  }

  clustering = ["customer_id"]

  labels = local.common_labels

  schema = jsonencode([
    { name = "customer_id",   type = "STRING",    mode = "NULLABLE" },
    { name = "first_name",    type = "STRING",    mode = "NULLABLE" },
    { name = "last_name",     type = "STRING",    mode = "NULLABLE" },
    { name = "date_of_birth", type = "DATE",      mode = "NULLABLE" },
    { name = "status",        type = "STRING",    mode = "NULLABLE" },
    { name = "account_count", type = "INTEGER",   mode = "NULLABLE" },
    { name = "total_balance", type = "FLOAT",     mode = "NULLABLE" },
    { name = "risk_score",    type = "INTEGER",   mode = "NULLABLE" },
    { name = "risk_category", type = "STRING",    mode = "NULLABLE" },
    { name = "updated_at",    type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# ============================================================================
# BIGQUERY — job_control dataset + tables
# ============================================================================

resource "google_bigquery_dataset" "job_control" {
  dataset_id = "job_control"
  location   = var.bq_location

  labels = local.common_labels
}

resource "google_bigquery_table" "pipeline_jobs" {
  dataset_id          = google_bigquery_dataset.job_control.dataset_id
  table_id            = "pipeline_jobs"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["system_id", "entity_type", "status"]

  labels = local.common_labels

  schema = jsonencode([
    { name = "run_id",         type = "STRING",    mode = "REQUIRED" },
    { name = "system_id",      type = "STRING",    mode = "REQUIRED" },
    { name = "entity_type",    type = "STRING",    mode = "REQUIRED" },
    { name = "extract_date",   type = "DATE",      mode = "NULLABLE" },
    { name = "status",         type = "STRING",    mode = "REQUIRED" },
    { name = "source_files",   type = "STRING",    mode = "REPEATED" },
    { name = "total_records",  type = "INT64",     mode = "NULLABLE" },
    { name = "started_at",     type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "completed_at",   type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "failed_at",      type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code",     type = "STRING",    mode = "NULLABLE" },
    { name = "error_message",  type = "STRING",    mode = "NULLABLE" },
    { name = "failure_stage",  type = "STRING",    mode = "NULLABLE" },
    { name = "error_file_path",type = "STRING",    mode = "NULLABLE" },
    { name = "created_at",     type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at",     type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "audit_trail" {
  dataset_id          = google_bigquery_dataset.job_control.dataset_id
  table_id            = "audit_trail"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["pipeline_name", "entity_type"]

  labels = local.common_labels

  schema = jsonencode([
    { name = "run_id",                       type = "STRING",    mode = "NULLABLE" },
    { name = "pipeline_name",                type = "STRING",    mode = "NULLABLE" },
    { name = "entity_type",                  type = "STRING",    mode = "NULLABLE" },
    { name = "source_file",                  type = "STRING",    mode = "NULLABLE" },
    { name = "record_count",                 type = "INTEGER",   mode = "NULLABLE" },
    { name = "processed_timestamp",          type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processing_duration_seconds",  type = "FLOAT",     mode = "NULLABLE" },
    { name = "success",                      type = "BOOLEAN",   mode = "NULLABLE" },
    { name = "error_count",                  type = "INTEGER",   mode = "NULLABLE" },
    { name = "audit_hash",                   type = "STRING",    mode = "NULLABLE" },
  ])
}
