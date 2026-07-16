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

# CDP dataset - Consumable Data Product (business-ready)
resource "google_bigquery_dataset" "cdp_generic" {
  dataset_id    = "cdp_generic"
  friendly_name = "CDP Generic - Consumable Data Product"
  description   = "Business-ready Generic data (customer_risk_profile)"
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
    { name = "event_key", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "ssn_masked", type = "STRING", mode = "NULLABLE" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "date_of_birth", type = "DATE", mode = "NULLABLE" },
    { name = "customer_status", type = "STRING", mode = "NULLABLE" },
    { name = "account_id", type = "STRING", mode = "NULLABLE" },
    { name = "account_type_desc", type = "STRING", mode = "NULLABLE" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "account_open_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])

  labels = local.common_labels
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
    { name = "portfolio_key", type = "STRING", mode = "NULLABLE" },
    { name = "decision_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "decision_code", type = "STRING", mode = "NULLABLE" },
    { name = "decision_outcome", type = "STRING", mode = "NULLABLE" },
    { name = "decision_date", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "score", type = "INTEGER", mode = "NULLABLE" },
    { name = "decision_reason", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])

  labels = local.common_labels
}

resource "google_bigquery_table" "fdp_portfolio_account_facility" {
  dataset_id          = google_bigquery_dataset.fdp_generic.dataset_id
  table_id            = "portfolio_account_facility"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }
  clustering = ["application_id", "customer_id"]

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "NULLABLE" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "loan_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE" },
    { name = "application_date", type = "DATE", mode = "NULLABLE" },
    { name = "application_status", type = "STRING", mode = "NULLABLE" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "account_type", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_extract_date", type = "DATE", mode = "NULLABLE" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])

  labels = local.common_labels
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

  # Schema mirrors BigQueryJobControlRepository#createJob's INSERT column list —
  # the code is authoritative (data-pipeline-gcp-bigquery-java/.../
  # BigQueryJobControlRepository.java). The previous schema here was the
  # predecessor-era shape (source_files REPEATED, total_records, max_retries,
  # parent_run_ids, dbt_model_name; no pipeline_name/record_count/FinOps
  # columns) — the first real deploy failed with "Column pipeline_name is not
  # present" (2026-07-10). Only run_id is REQUIRED: the adapter binds every
  # other column as a nullable named parameter.
  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "system_id", type = "STRING", mode = "NULLABLE" },
    { name = "pipeline_name", type = "STRING", mode = "NULLABLE" },
    { name = "extract_date", type = "DATE", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "job_type", type = "STRING", mode = "NULLABLE" },
    { name = "entity_type", type = "STRING", mode = "NULLABLE" },
    { name = "source_file", type = "STRING", mode = "NULLABLE" },
    { name = "target_table", type = "STRING", mode = "NULLABLE" },
    { name = "record_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "error_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "retry_count", type = "INTEGER", mode = "NULLABLE" },
    { name = "failure_stage", type = "STRING", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_file_path", type = "STRING", mode = "NULLABLE" },
    { name = "estimated_cost_usd", type = "FLOAT", mode = "NULLABLE" },
    { name = "billed_bytes_scanned", type = "INTEGER", mode = "NULLABLE" },
    { name = "billed_bytes_written", type = "INTEGER", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "started_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "completed_at", type = "TIMESTAMP", mode = "NULLABLE" }
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

# Cloud Composer service account (only when Composer is enabled)
resource "google_service_account" "generic_composer" {
  count        = var.enable_composer ? 1 : 0
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

resource "google_bigquery_dataset_iam_member" "generic_dbt_cdp_editor" {
  dataset_id = google_bigquery_dataset.cdp_generic.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "generic_dbt_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

# --- Composer IAM (only when Composer is enabled) ---

resource "google_project_iam_member" "generic_composer_worker" {
  count   = var.enable_composer ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.generic_composer[0].email}"
}

resource "google_project_iam_member" "generic_composer_dataflow" {
  count   = var.enable_composer ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.generic_composer[0].email}"
}

resource "google_project_iam_member" "generic_composer_bigquery" {
  count   = var.enable_composer ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.generic_composer[0].email}"
}

resource "google_project_iam_member" "generic_composer_storage" {
  count   = var.enable_composer ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.generic_composer[0].email}"
}

resource "google_pubsub_subscription_iam_member" "generic_composer_subscriber" {
  count        = var.enable_composer ? 1 : 0
  subscription = google_pubsub_subscription.generic_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.generic_composer[0].email}"
}

# ============================================================================
# CLOUD COMPOSER (APACHE AIRFLOW)
# ============================================================================

resource "google_composer_environment" "generic_composer" {
  count  = var.enable_composer ? 1 : 0
  name   = "${local.prefix}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = "composer-2.16.1-airflow-2.10.5"

      # Only install orchestration-specific packages (NO beam to avoid Airflow conflicts)
      pypi_packages = {
        culvert = "[orchestration]==0.1.1"
      }

      env_variables = {
        GCP_PROJECT_ID    = var.gcp_project_id
        EM_LANDING_BUCKET = google_storage_bucket.landing.name
        EM_ARCHIVE_BUCKET = google_storage_bucket.archive.name
        EM_ERROR_BUCKET   = google_storage_bucket.error.name
        ODP_DATASET       = google_bigquery_dataset.odp_generic.dataset_id
        FDP_DATASET       = google_bigquery_dataset.fdp_generic.dataset_id
        CDP_DATASET       = google_bigquery_dataset.cdp_generic.dataset_id
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
      service_account = google_service_account.generic_composer[0].email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.generic_composer_worker,
  ]
}

# ============================================================================
# FDP TRIGGER (Cloud Run + Cloud Scheduler)
# ============================================================================
# Replaces Composer/Airflow as the trigger for mainframe-segment-transform.
# Polls the producing team's FDP partitions via INFORMATION_SCHEMA.
# See docs/FDP_CONSUMER_ARCHITECTURE.md for the full design.
# ============================================================================

# Service account for the Cloud Run trigger service
resource "google_service_account" "fdp_trigger" {
  count        = var.enable_fdp_trigger ? 1 : 0
  account_id   = "fdp-trigger-sa"
  display_name = "FDP Trigger Cloud Run Service Account"
  description  = "Polls FDP readiness and launches mainframe-segment-transform Dataflow"
}

# IAM: read FDP metadata in the producing team's project
# (granted via the producing team's project; this Terraform asserts the binding
# exists in our state but the actual grant must be approved by them)
resource "google_project_iam_member" "fdp_trigger_metadata_viewer" {
  count   = var.enable_fdp_trigger && var.fdp_project_id != "" ? 1 : 0
  project = var.fdp_project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

resource "google_project_iam_member" "fdp_trigger_data_viewer" {
  count   = var.enable_fdp_trigger && var.fdp_project_id != "" ? 1 : 0
  project = var.fdp_project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# IAM: write to job_control in our project
resource "google_bigquery_dataset_iam_member" "fdp_trigger_job_control_editor" {
  count      = var.enable_fdp_trigger ? 1 : 0
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# IAM: read job_control (for dedup query)
resource "google_bigquery_dataset_iam_member" "fdp_trigger_job_control_viewer" {
  count      = var.enable_fdp_trigger ? 1 : 0
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# IAM: BigQuery job user (run queries)
resource "google_project_iam_member" "fdp_trigger_bq_job_user" {
  count   = var.enable_fdp_trigger ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# IAM: launch Dataflow Flex Templates
resource "google_project_iam_member" "fdp_trigger_dataflow_developer" {
  count   = var.enable_fdp_trigger ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/dataflow.developer"
  member  = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# IAM: act as the Dataflow worker SA (required to launch Dataflow as another SA)
resource "google_service_account_iam_member" "fdp_trigger_act_as_dataflow" {
  count              = var.enable_fdp_trigger ? 1 : 0
  service_account_id = google_service_account.generic_dataflow.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.fdp_trigger[0].email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "fdp_trigger" {
  count    = var.enable_fdp_trigger ? 1 : 0
  name     = "fdp-trigger"
  location = var.gcp_region
  # INTERNAL_ONLY: only Cloud Scheduler (via OIDC) and other GCP services
  # in the same project can invoke. Public internet is blocked.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.fdp_trigger[0].email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    timeout = "300s"

    containers {
      image = "gcr.io/${var.gcp_project_id}/fdp-trigger:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GCP_PROJECT"
        value = var.gcp_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.gcp_region
      }
      env {
        name  = "FDP_PROJECT"
        value = var.fdp_project_id
      }
      env {
        name  = "FDP_DATASET"
        value = var.fdp_dataset
      }
      env {
        name  = "FDP_TABLES"
        value = join(",", var.fdp_tables)
      }
      env {
        name  = "STABILITY_MINUTES"
        value = tostring(var.fdp_stability_minutes)
      }
      env {
        name  = "TEMPLATE_GCS_PATH"
        value = "gs://${var.gcp_project_id}-generic-${var.environment}-segments/templates/segment_transform.json"
      }
      env {
        name  = "OUTPUT_BUCKET"
        value = "${var.gcp_project_id}-generic-${var.environment}-segments"
      }
      env {
        name  = "JOB_CONTROL_TABLE"
        value = "${var.gcp_project_id}.${google_bigquery_dataset.job_control.dataset_id}.pipeline_jobs"
      }
      env {
        name  = "DATAFLOW_SERVICE_ACCOUNT"
        value = google_service_account.generic_dataflow.email
      }
      env {
        name  = "TEMP_LOCATION"
        value = "gs://${google_storage_bucket.temp.name}/dataflow"
      }
      env {
        name  = "DEFAULT_SEGMENT"
        value = var.fdp_trigger_default_segment
      }
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.fdp_trigger_bq_job_user,
    google_project_iam_member.fdp_trigger_dataflow_developer,
  ]
}

# Service account for Cloud Scheduler to invoke Cloud Run
resource "google_service_account" "fdp_trigger_scheduler" {
  count        = var.enable_fdp_trigger ? 1 : 0
  account_id   = "fdp-trigger-scheduler-sa"
  display_name = "Cloud Scheduler invoker for fdp-trigger"
}

# Allow scheduler SA to invoke the Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "fdp_trigger_invoker" {
  count    = var.enable_fdp_trigger ? 1 : 0
  project  = var.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.fdp_trigger[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.fdp_trigger_scheduler[0].email}"
}

# Cloud Scheduler job that polls every 10 minutes during the expected window
resource "google_cloud_scheduler_job" "fdp_trigger_poller" {
  count       = var.enable_fdp_trigger ? 1 : 0
  name        = "fdp-trigger-poller"
  region      = var.gcp_region
  description = "Poll FDP readiness and launch mainframe-segment-transform if ready"
  schedule    = var.fdp_trigger_schedule
  time_zone   = "Etc/UTC"

  attempt_deadline = "300s"

  retry_config {
    retry_count          = 1
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
    max_doublings        = 1
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.fdp_trigger[0].uri}/trigger"

    headers = {
      "Content-Type" = "application/json"
    }

    # Empty body -- service defaults extract_date to today
    body = base64encode("{}")

    oidc_token {
      service_account_email = google_service_account.fdp_trigger_scheduler[0].email
      audience              = google_cloud_run_v2_service.fdp_trigger[0].uri
    }
  }
}

# =============================================================================
# MONTHLY CDP + SEGMENT PIPELINE
#
# Flow:
#   Cloud Scheduler (2nd of month) → cdp-monthly-refresh Cloud Build
#     → FDP readiness check → dbt CDP run → dbt test
#     → triggers monthly-segment-transform Cloud Build
#       → CDP readiness check → Dataflow launch
#
# Manual re-runs:
#   Re-run full chain:  gcloud builds triggers run cdp-monthly-refresh --branch=main
#   Re-run segment only: gcloud builds triggers run monthly-segment-transform --branch=main
#
# Prerequisites:
#   - GitHub App connected to Cloud Build for var.github_repo
#     (one-time setup: GCP Console → Cloud Build → Repositories → Connect)
#   - generic-cdp-transformation Docker image exists in GCR
#     (built by: gcloud builds submit --config deployments/fdp-to-consumable-product/cloudbuild.yaml)
#   - generic-segment-transform Flex Template uploaded to GCS
#     (built by: gcloud builds submit --config deployments/mainframe-segment-transform/cloudbuild.yaml)
# =============================================================================

# Project number — needed to reference the default Cloud Build SA
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# Allow the default Cloud Build SA to trigger other Cloud Build builds
# (needed for the CDP build to chain into the segment-transform build)
resource "google_project_iam_member" "cloudbuild_sa_trigger_builds" {
  count   = var.enable_monthly_segment ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# ---------------------------------------------------------------------------
# CDP refresh: Cloud Build trigger + Cloud Scheduler (2nd of month)
# ---------------------------------------------------------------------------

# Service account for Cloud Scheduler → CDP Cloud Build
resource "google_service_account" "cdp_monthly_scheduler" {
  count        = var.enable_monthly_segment ? 1 : 0
  project      = var.gcp_project_id
  account_id   = "cdp-monthly-sa"
  display_name = "Monthly CDP refresh — Cloud Scheduler invoker"
}

resource "google_project_iam_member" "cdp_monthly_cloudbuild" {
  count   = var.enable_monthly_segment ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.cdp_monthly_scheduler[0].email}"
}

# Cloud Build trigger for CDP refresh
resource "google_cloudbuild_trigger" "cdp_refresh" {
  count       = var.enable_monthly_segment ? 1 : 0
  project     = var.gcp_project_id
  name        = "cdp-monthly-refresh"
  description = "Monthly CDP refresh: FDP readiness check → dbt run → dbt test → trigger segment"

  source_to_build {
    uri       = "https://github.com/${var.github_repo}"
    ref       = "refs/heads/main"
    repo_type = "GITHUB"
  }

  git_file_source {
    path      = "deployments/fdp-to-consumable-product/cloudbuild-monthly.yaml"
    uri       = "https://github.com/${var.github_repo}"
    revision  = "refs/heads/main"
    repo_type = "GITHUB"
  }

  substitutions = {
    _ENVIRONMENT   = var.environment
    _FDP_PROJECT   = var.fdp_project_id
    _FDP_DATASET   = var.fdp_dataset != "" ? var.fdp_dataset : "fdp_dataset"
    _EXTRACT_MONTH = ""
  }
}

# Cloud Scheduler: fires on 2nd of each month at 06:00 UTC
resource "google_cloud_scheduler_job" "cdp_refresh" {
  count       = var.enable_monthly_segment ? 1 : 0
  name        = "cdp-monthly-refresh"
  region      = var.gcp_region
  description = "Trigger monthly CDP refresh on 2nd of each month (chains to segment-extract on success)"
  schedule    = var.cdp_refresh_schedule
  time_zone   = "Etc/UTC"

  attempt_deadline = "30s"

  retry_config {
    retry_count          = 0
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri         = "https://cloudbuild.googleapis.com/v1/projects/${var.gcp_project_id}/triggers/${google_cloudbuild_trigger.cdp_refresh[0].trigger_id}:run"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      branchName = "main"
    }))

    oauth_token {
      service_account_email = google_service_account.cdp_monthly_scheduler[0].email
    }
  }

  depends_on = [google_project_iam_member.cdp_monthly_cloudbuild]
}

# ---------------------------------------------------------------------------
# Segment extract: Cloud Build trigger (called by CDP build, or manually)
# Cloud Scheduler removed — segment is chained from CDP, not time-triggered
# ---------------------------------------------------------------------------

# Cloud Build trigger for segment-extract (chained from CDP, or triggered manually)
# NOTE: no Cloud Scheduler — segment is triggered by the CDP build on success.
# NOTE: requires GitHub App to be connected in Cloud Build before terraform apply.
resource "google_cloudbuild_trigger" "monthly_segment" {
  count       = var.enable_monthly_segment ? 1 : 0
  project     = var.gcp_project_id
  name        = "monthly-segment-transform"
  description = "Mainframe segment extract: CDP readiness check → Dataflow launch (chained from cdp-monthly-refresh)"

  source_to_build {
    uri       = "https://github.com/${var.github_repo}"
    ref       = "refs/heads/main"
    repo_type = "GITHUB"
  }

  git_file_source {
    path      = "deployments/mainframe-segment-transform/cloudbuild-monthly.yaml"
    uri       = "https://github.com/${var.github_repo}"
    revision  = "refs/heads/main"
    repo_type = "GITHUB"
  }

  substitutions = {
    _OUTPUT_BUCKET = "${var.gcp_project_id}-generic-${var.environment}-segments"
    _SEGMENT       = var.monthly_segment_segments
    _EXTRACT_MONTH = ""
    _REGION        = var.gcp_region
  }
}
