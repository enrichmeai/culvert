# Generic Pipeline - Unified Terraform Configuration
#
# Provisions complete GCP infrastructure for Generic pipeline:
# - GCS buckets (landing, archive, error)
# - BigQuery datasets (odp_generic, fdp_generic, job_control)
# - BigQuery tables (ODP, FDP, job_control)
# - Pub/Sub topics and subscriptions
# - Service accounts and IAM roles
# - Cloud Composer environment
#
# Generic System Overview:
# - 4 source entities: Customers, Accounts, Decision, Applications
# - 4 ODP tables: odp_generic.customers, odp_generic.accounts, odp_generic.decision, odp_generic.applications
# - 3 FDP tables: fdp_generic.event_transaction_excess, portfolio_account_excess, portfolio_account_facility
# - Dependency wait: All 3 JOIN entities must be loaded before FDP transformation

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
    bucket = "gcp-pipeline-terraform-state"
    prefix = "generic"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "google-beta" {
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
  system_id   = "generic"

  # Resource naming convention
  prefix = "generic-${local.environment}"

  common_labels = {
    project     = "gcp-pipeline-builder"
    system      = "generic"
    environment = local.environment
    managed_by  = "terraform"
  }

  # Generic entity configuration
  generic_entities = ["customers", "accounts", "decision", "applications"]
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Landing bucket for incoming Generic files
resource "google_storage_bucket" "landing" {
  name          = "${var.gcp_project_id}-${local.prefix}-landing"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  # Move to coldline after 90 days
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

# Create entity subfolders in landing bucket
resource "google_storage_bucket_object" "entity_folders" {
  for_each = toset(local.generic_entities)

  name    = "generic/${each.value}/.keep"
  content = "# Placeholder for ${each.value} entity files"
  bucket  = google_storage_bucket.landing.name
}

# Archive bucket for processed Generic files
resource "google_storage_bucket" "archive" {
  name          = "${var.gcp_project_id}-${local.prefix}-archive"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = true # Always version archives
  }

  # Move to coldline after 1 year
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Move to archive after 5 years
  lifecycle_rule {
    condition {
      age = 1825
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = local.common_labels
}

# Error bucket for failed Generic files
resource "google_storage_bucket" "error" {
  name          = "${var.gcp_project_id}-${local.prefix}-error"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Delete error files after 90 days
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

# Temp bucket for Dataflow templates and staging
resource "google_storage_bucket" "temp" {
  name          = "${var.gcp_project_id}-${local.prefix}-temp"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

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
# PUB/SUB - FILE NOTIFICATIONS
# ============================================================================

# Topic for Generic file landing notifications
resource "google_pubsub_topic" "generic_file_notifications" {
  name = "generic-file-notifications"

  labels = local.common_labels
}

# Subscription for Generic file notifications
resource "google_pubsub_subscription" "generic_file_notifications_sub" {
  name  = "generic-file-notifications-sub"
  topic = google_pubsub_topic.generic_file_notifications.name

  ack_deadline_seconds = 60

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.generic_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "generic_dead_letter" {
  name = "generic-file-notifications-dead-letter"

  labels = local.common_labels
}

# GCS notification to Pub/Sub (triggers on file upload)
resource "google_storage_notification" "generic_file_notification" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.generic_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]

  # Only notify for files under generic/ prefix
  object_name_prefix = "generic/"

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# Allow GCS to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.generic_file_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# Get GCS service account
data "google_storage_project_service_account" "gcs_account" {
  project = var.gcp_project_id
}

# ============================================================================
# BIGQUERY DATASETS
# ============================================================================

# ODP dataset - Original Data Product (raw 1:1 mapping)
resource "google_bigquery_dataset" "odp_generic" {
  dataset_id    = "odp_generic"
  friendly_name = "ODP Generic - Original Data Product"
  description   = "Raw data from Generic mainframe extracts (customers, accounts, decision, applications)"
  location      = var.bq_location

  labels = local.common_labels

  lifecycle { ignore_changes = [location] }
}

# FDP dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_generic" {
  dataset_id    = "fdp_generic"
  friendly_name = "FDP Generic - Foundation Data Product"
  description   = "Transformed Generic data (event_transaction_excess, portfolio_account_excess, portfolio_account_facility)"
  location      = var.bq_location

  labels = local.common_labels

  lifecycle { ignore_changes = [location] }
}

# Job control dataset (shared across systems)
resource "google_bigquery_dataset" "job_control" {
  dataset_id    = "job_control"
  friendly_name = "Pipeline Job Control"
  description   = "Job tracking and status for all pipelines"
  location      = var.bq_location

  labels = local.common_labels

  lifecycle { ignore_changes = [location] }
}

# ============================================================================
# BIGQUERY TABLES — ODP (Original Data Product)
# ============================================================================

resource "google_bigquery_table" "odp_customers" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "customers"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_date"
  }
  clustering = ["_run_id", "status"]

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "ssn", type = "STRING", mode = "NULLABLE" },
    { name = "dob", type = "DATE", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "created_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_customers_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "customers_errors"
  deletion_protection = false

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_accounts" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "accounts"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "open_date"
  }
  clustering = ["_run_id", "account_type"]

  schema = jsonencode([
    { name = "account_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "account_type", type = "STRING", mode = "NULLABLE" },
    { name = "balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "open_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_accounts_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "accounts_errors"
  deletion_protection = false

  schema = jsonencode([
    { name = "account_id", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_decision" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "decision"
  deletion_protection = false

  clustering = ["_run_id", "decision_code"]

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "application_id", type = "STRING", mode = "NULLABLE" },
    { name = "decision_code", type = "STRING", mode = "NULLABLE" },
    { name = "decision_date", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "score", type = "INTEGER", mode = "NULLABLE" },
    { name = "reason_codes", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_decision_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "decision_errors"
  deletion_protection = false

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_applications" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "applications"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "application_date"
  }

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "loan_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE" },
    { name = "application_date", type = "DATE", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "account_type", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "odp_applications_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "applications_errors"
  deletion_protection = false

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "STRING", mode = "NULLABLE" },
    { name = "error_type", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

# ============================================================================
# BIGQUERY TABLES — FDP (Foundation Data Product)
# ============================================================================

resource "google_bigquery_table" "fdp_event_transaction_excess" {
  dataset_id          = google_bigquery_dataset.fdp_generic.dataset_id
  table_id            = "event_transaction_excess"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }
  clustering = ["customer_id", "account_id"]

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "account_id", type = "STRING", mode = "REQUIRED" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "fdp_portfolio_account_excess" {
  dataset_id          = google_bigquery_dataset.fdp_generic.dataset_id
  table_id            = "portfolio_account_excess"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }
  clustering = ["customer_id", "_run_id"]

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED" },
    { name = "score", type = "INTEGER", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

resource "google_bigquery_table" "fdp_portfolio_account_facility" {
  dataset_id          = google_bigquery_dataset.fdp_generic.dataset_id
  table_id            = "portfolio_account_facility"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }
  clustering = ["customer_id", "account_id"]

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "account_id", type = "STRING", mode = "REQUIRED" },
    { name = "loan_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

# ============================================================================
# BIGQUERY TABLES — Job Control
# ============================================================================

resource "google_bigquery_table" "pipeline_jobs" {
  dataset_id          = google_bigquery_dataset.job_control.dataset_id
  table_id            = "pipeline_jobs"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
  clustering = ["system_id", "entity_type", "status"]

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "system_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED" },
    { name = "extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "started_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "completed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "failed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "source_files", type = "STRING", mode = "REPEATED" },
    { name = "total_records", type = "INTEGER", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_file_path", type = "STRING", mode = "NULLABLE" },
    { name = "failure_stage", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "job_type", type = "STRING", mode = "NULLABLE" },
    { name = "retry_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "max_retries", type = "INTEGER", mode = "NULLABLE" },
    { name = "parent_run_ids", type = "STRING", mode = "REPEATED" },
    { name = "dbt_model_name", type = "STRING", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
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

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "NULLABLE" },
    { name = "pipeline_name", type = "STRING", mode = "NULLABLE" },
    { name = "entity_type", type = "STRING", mode = "NULLABLE" },
    { name = "source_file", type = "STRING", mode = "NULLABLE" },
    { name = "record_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "processed_timestamp", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "processing_duration_seconds", type = "FLOAT", mode = "NULLABLE" },
    { name = "success", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "error_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "audit_hash", type = "STRING", mode = "NULLABLE" }
  ])

  labels = local.common_labels
  lifecycle { ignore_changes = [schema] }
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# Dataflow service account for Generic pipelines
resource "google_service_account" "generic_dataflow" {
  account_id   = "${local.prefix}-dataflow"
  display_name = "Generic Dataflow Service Account"
  description  = "Service account for Generic Dataflow pipeline execution"
}

# dbt service account for Generic transformations
resource "google_service_account" "generic_dbt" {
  account_id   = "${local.prefix}-dbt"
  display_name = "Generic dbt Service Account"
  description  = "Service account for Generic dbt transformations"
}

# Cloud Composer service account
resource "google_service_account" "generic_composer" {
  account_id   = "generic-composer-sa"
  display_name = "Generic Cloud Composer Service Account"
}

# ============================================================================
# IAM ROLES & PERMISSIONS
# ============================================================================

# --- Dataflow IAM ---

resource "google_project_iam_member" "generic_dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_storage_bucket_iam_member" "generic_dataflow_landing" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_storage_bucket_iam_member" "generic_dataflow_archive" {
  bucket = google_storage_bucket.archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_storage_bucket_iam_member" "generic_dataflow_error" {
  bucket = google_storage_bucket.error.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_bigquery_dataset_iam_member" "generic_dataflow_odp" {
  dataset_id = google_bigquery_dataset.odp_generic.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_bigquery_dataset_iam_member" "generic_dataflow_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

resource "google_pubsub_subscription_iam_member" "generic_dataflow_subscriber" {
  subscription = google_pubsub_subscription.generic_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

# --- dbt IAM ---

resource "google_bigquery_dataset_iam_member" "generic_dbt_odp_reader" {
  dataset_id = google_bigquery_dataset.odp_generic.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "generic_dbt_fdp_editor" {
  dataset_id = google_bigquery_dataset.fdp_generic.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "generic_dbt_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

# --- Composer IAM ---

resource "google_project_iam_member" "generic_composer_worker" {
  project = var.gcp_project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_project_iam_member" "generic_composer_dataflow" {
  project = var.gcp_project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_project_iam_member" "generic_composer_bigquery" {
  project = var.gcp_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_project_iam_member" "generic_composer_storage" {
  project = var.gcp_project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_pubsub_subscription_iam_member" "generic_composer_subscriber" {
  subscription = google_pubsub_subscription.generic_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.generic_composer.email}"
}

# ============================================================================
# CLOUD COMPOSER (APACHE AIRFLOW)
# ============================================================================

resource "google_composer_environment" "generic_composer" {
  name   = "${local.prefix}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = "composer-2.16.1-airflow-2.10.5"

      # Only install orchestration-specific packages (NO beam to avoid Airflow conflicts)
      pypi_packages = {
        gcp-pipeline-core          = "==1.0.13"
        gcp-pipeline-orchestration = "==1.0.13"
      }

      env_variables = {
        GCP_PROJECT_ID    = var.gcp_project_id
        EM_LANDING_BUCKET = google_storage_bucket.landing.name
        EM_ARCHIVE_BUCKET = google_storage_bucket.archive.name
        EM_ERROR_BUCKET   = google_storage_bucket.error.name
        ODP_DATASET       = google_bigquery_dataset.odp_generic.dataset_id
        FDP_DATASET       = google_bigquery_dataset.fdp_generic.dataset_id
        JOB_CONTROL_TABLE = "${google_bigquery_dataset.job_control.dataset_id}.pipeline_jobs"
      }
    }

    workloads_config {
      scheduler {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }
      web_server {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
      }
      worker {
        cpu        = 1
        memory_gb  = 4
        storage_gb = 2
        min_count  = 1
        max_count  = 3
      }
    }

    environment_size = "ENVIRONMENT_SIZE_SMALL"

    node_config {
      service_account = google_service_account.generic_composer.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.generic_composer_worker,
  ]
}
