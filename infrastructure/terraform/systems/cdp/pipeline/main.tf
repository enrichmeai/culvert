# CDP (Consumable Data Product) - Terraform Main Configuration

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
    prefix = "cdp/staging"
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
  environment = var.environment
  project_id  = var.gcp_project_id
  region      = var.gcp_region
  system_id   = var.cdp_system_id

  # Resource naming convention
  prefix = "${local.system_id}-${local.environment}"

  common_labels = {
    project     = "gcp-pipeline-builder"
    system      = local.system_id
    environment = local.environment
    managed_by  = "terraform"
  }
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Target bucket for CDP segmented exports
resource "google_storage_bucket" "cdp_output" {
  name          = "${var.gcp_project_id}-${local.prefix}-output"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Life cycle: Delete after 30 days (CDPs are often ephemeral/cached)
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# Dedicated Service Account for CDP Dataflow Job
resource "google_service_account" "cdp_dataflow_sa" {
  account_id   = "${local.prefix}-dataflow-sa"
  display_name = "CDP Dataflow Service Account"
}

# IAM: Read from source FDP BigQuery dataset
resource "google_bigquery_dataset_iam_member" "fdp_reader" {
  dataset_id = var.fdp_dataset
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.cdp_dataflow_sa.email}"
}

# IAM: Write to target CDP GCS bucket
resource "google_storage_bucket_iam_member" "gcs_writer" {
  bucket = google_storage_bucket.cdp_output.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cdp_dataflow_sa.email}"
}

# IAM: Dataflow Worker permissions
resource "google_project_iam_member" "dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.cdp_dataflow_sa.email}"
}

# IAM: BigQuery Job User (needed to run queries)
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cdp_dataflow_sa.email}"
}
