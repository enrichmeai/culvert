# LOA Blueprint - Terraform Main Configuration
#
# Provisions complete GCP infrastructure for LOA pipeline:
# - GCS buckets (input, archive, error, quarantine)
# - BigQuery datasets (raw, staging, marts)
# - Service accounts and IAM roles
# - Network configuration
# - Resource dependencies

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "loa-terraform-state"
    prefix = "staging"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = "europe-west2" # London, UK
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = "europe-west2" # London, UK
}

# ============================================================================
# LOCAL VARIABLES
# ============================================================================

locals {
  environment = var.environment
  project_id  = var.gcp_project_id
  region      = var.gcp_region

  # Resource naming convention
  prefix = "loa-${local.environment}"

  common_labels = {
    project     = "loa-blueprint"
    environment = local.environment
    managed_by  = "terraform"
    created_at  = timestamp()
  }
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Input bucket for incoming files
resource "google_storage_bucket" "input" {
  name          = "${local.prefix}-input"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = local.common_labels
}

# Archive bucket for processed files
resource "google_storage_bucket" "archive" {
  name          = "${local.prefix}-archive"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = true # Always version archives
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 1825 # 5 years
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = local.common_labels
}

# Error bucket for failed files
resource "google_storage_bucket" "error" {
  name          = "${local.prefix}-error"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

# Quarantine bucket for malformed files
resource "google_storage_bucket" "quarantine" {
  name          = "${local.prefix}-quarantine"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY DATASETS
# ============================================================================

# Raw data dataset
resource "google_bigquery_dataset" "raw" {
  dataset_id    = "raw"
  friendly_name = "Raw Data - Ingested Files"
  description   = "Raw data loaded directly from source files"
  location      = var.bq_location

  access {
    role          = "OWNER"
    user_by_email = var.dataflow_service_account
  }

  access {
    role          = "READER"
    user_by_email = var.analytics_service_account
  }

  labels = local.common_labels
}

# Staging dataset
resource "google_bigquery_dataset" "staging" {
  dataset_id    = "staging"
  friendly_name = "Staging Data - dbt Transformations"
  description   = "Intermediate transformations from raw data"
  location      = var.bq_location

  access {
    role          = "OWNER"
    user_by_email = var.dbt_service_account
  }

  labels = local.common_labels
}

# Marts dataset (analytics)
resource "google_bigquery_dataset" "marts" {
  dataset_id    = "marts"
  friendly_name = "Analytics Mart - Final Models"
  description   = "Analytics-ready models for reporting"
  location      = var.bq_location

  access {
    role          = "READER"
    user_by_email = var.analytics_service_account
  }

  labels = local.common_labels
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# Dataflow service account
resource "google_service_account" "dataflow" {
  account_id   = "${local.prefix}-dataflow"
  display_name = "LOA Dataflow Service Account"
  description  = "Service account for Dataflow pipeline execution"
}

# dbt service account
resource "google_service_account" "dbt" {
  account_id   = "${local.prefix}-dbt"
  display_name = "LOA dbt Service Account"
  description  = "Service account for dbt transformations"
}

# Cloud Run service account
resource "google_service_account" "cloud_run" {
  account_id   = "${local.prefix}-cloud-run"
  display_name = "LOA Cloud Run Service Account"
  description  = "Service account for Cloud Run services"
}

# Analytics service account
resource "google_service_account" "analytics" {
  account_id   = "${local.prefix}-analytics"
  display_name = "LOA Analytics Service Account"
  description  = "Service account for analytics/reporting access"
}

# ============================================================================
# IAM ROLES & PERMISSIONS
# ============================================================================

# Dataflow permissions
resource "google_project_iam_member" "dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_storage_bucket_iam_member" "dataflow_input" {
  bucket = google_storage_bucket.input.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_storage_bucket_iam_member" "dataflow_archive" {
  bucket = google_storage_bucket.archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_storage_bucket_iam_member" "dataflow_error" {
  bucket = google_storage_bucket.error.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow.email}"
}

# BigQuery permissions for Dataflow
resource "google_bigquery_dataset_iam_member" "dataflow_raw_editor" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dataflow.email}"
}

# dbt permissions
resource "google_bigquery_dataset_iam_member" "dbt_staging_editor" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_marts_editor" {
  dataset_id = google_bigquery_dataset.marts.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_raw_reader" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

# Cloud Run permissions
resource "google_project_iam_member" "cloud_run_sa_user" {
  project = var.gcp_project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Analytics read-only access
resource "google_bigquery_dataset_iam_member" "analytics_raw_reader" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.analytics.email}"
}

resource "google_bigquery_dataset_iam_member" "analytics_marts_reader" {
  dataset_id = google_bigquery_dataset.marts.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.analytics.email}"
}

# ============================================================================
# NETWORKING
# ============================================================================

# VPC Network
resource "google_compute_network" "main" {
  name                    = "${local.prefix}-network"
  auto_create_subnetworks = false
}

# Subnet
resource "google_compute_subnetwork" "main" {
  name          = "${local.prefix}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.main.id

  private_ip_google_access = true
}

# Cloud NAT for outbound traffic
resource "google_compute_router" "main" {
  name    = "${local.prefix}-router"
  region  = var.gcp_region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "${local.prefix}-nat"
  router                             = google_compute_router.main.name
  region                             = var.gcp_region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# ============================================================================
# MONITORING
# ============================================================================

# Log bucket for LOA pipeline logs
resource "google_logging_project_bucket_config" "loa_logs" {
  project          = var.gcp_project_id
  location         = var.gcp_region
  bucket_id        = "loa-pipeline-logs"
  retention_days   = var.log_retention_days
  enable_analytics = true
}

