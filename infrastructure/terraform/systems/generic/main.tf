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
}

# FDP dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_generic" {
  dataset_id    = "fdp_generic"
  friendly_name = "FDP Generic - Foundation Data Product"
  description   = "Transformed Generic data (event_transaction_excess, portfolio_account_excess, portfolio_account_facility)"
  location      = var.bq_location

  labels = local.common_labels
}

# Job control dataset (shared across systems)
resource "google_bigquery_dataset" "job_control" {
  dataset_id    = "job_control"
  friendly_name = "Pipeline Job Control"
  description   = "Job tracking and status for all pipelines"
  location      = var.bq_location

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY TABLES - ODP (Customers, Accounts, Decision, Applications)
# ============================================================================

# ODP: Customers table
resource "google_bigquery_table" "odp_customers" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "customers"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "_run_id"]

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "first_name", type = "STRING", mode = "NULLABLE", description = "First name" },
    { name = "last_name", type = "STRING", mode = "NULLABLE", description = "Last name" },
    { name = "ssn", type = "STRING", mode = "NULLABLE", description = "Social Security Number (PII)" },
    { name = "dob", type = "DATE", mode = "NULLABLE", description = "Date of birth (PII)" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "A=Active, I=Inactive, C=Closed" },
    { name = "created_date", type = "DATE", mode = "NULLABLE", description = "Customer creation date" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Customers errors table
resource "google_bigquery_table" "odp_customers_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "customers_errors"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Accounts table
resource "google_bigquery_table" "odp_accounts" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "accounts"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["account_id", "customer_id", "_run_id"]

  schema = jsonencode([
    { name = "account_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Foreign key to customers" },
    { name = "account_type", type = "STRING", mode = "NULLABLE", description = "CHECKING, SAVINGS, MONEY_MARKET, CD, IRA" },
    { name = "balance", type = "NUMERIC", mode = "NULLABLE", description = "Current balance" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "A=Active, I=Inactive, C=Closed" },
    { name = "open_date", type = "DATE", mode = "NULLABLE", description = "Account open date" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Accounts errors table
resource "google_bigquery_table" "odp_accounts_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "accounts_errors"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Decision table
resource "google_bigquery_table" "odp_decision" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "decision"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["decision_id", "customer_id", "_run_id"]

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Foreign key to customers" },
    { name = "application_id", type = "STRING", mode = "NULLABLE", description = "Related application" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED", description = "APPROVE, DECLINE, REVIEW, PENDING" },
    { name = "decision_date", type = "TIMESTAMP", mode = "REQUIRED", description = "When decision was made" },
    { name = "score", type = "INTEGER", mode = "NULLABLE", description = "Credit score (300-850)" },
    { name = "reason_codes", type = "STRING", mode = "NULLABLE", description = "Pipe-separated reason codes" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Decision errors table
resource "google_bigquery_table" "odp_decision_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "decision_errors"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Applications table
resource "google_bigquery_table" "odp_applications" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "applications"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["application_id", "customer_id", "_run_id"]

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Foreign key to customers" },
    { name = "ssn", type = "STRING", mode = "NULLABLE", description = "Social Security Number (PII)" },
    { name = "loan_amount", type = "NUMERIC", mode = "NULLABLE", description = "Requested loan amount" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE", description = "Interest rate" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE", description = "Loan term in months" },
    { name = "application_date", type = "DATE", mode = "NULLABLE", description = "Application date" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "Application status" },
    { name = "event_type", type = "STRING", mode = "NULLABLE", description = "Event type" },
    { name = "account_type", type = "STRING", mode = "NULLABLE", description = "Account type (PORTFOLIO, EXCESS)" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ODP: Applications errors table
resource "google_bigquery_table" "odp_applications_errors" {
  dataset_id          = google_bigquery_dataset.odp_generic.dataset_id
  table_id            = "applications_errors"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ============================================================================
# BIGQUERY TABLES - FDP (Foundation Data Products)
# ============================================================================

# FDP: Event Transaction Excess (JOIN: customers + accounts)
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
    { name = "event_key", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "ssn_masked", type = "STRING", mode = "NULLABLE" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "date_of_birth", type = "DATE", mode = "NULLABLE" },
    { name = "customer_status", type = "STRING", mode = "NULLABLE" },
    { name = "account_id", type = "STRING", mode = "REQUIRED" },
    { name = "account_type_desc", type = "STRING", mode = "NULLABLE" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "account_open_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# FDP: Portfolio Account Excess (JOIN: customers + decision)
resource "google_bigquery_table" "fdp_portfolio_account_excess" {
  dataset_id          = google_bigquery_dataset.fdp_generic.dataset_id
  table_id            = "portfolio_account_excess"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "decision_id"]

  schema = jsonencode([
    { name = "portfolio_key", type = "STRING", mode = "REQUIRED" },
    { name = "decision_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED" },
    { name = "decision_outcome", type = "STRING", mode = "NULLABLE" },
    { name = "decision_date", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "score", type = "INTEGER", mode = "NULLABLE" },
    { name = "decision_reason", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# FDP: Portfolio Account Facility (MAP: applications)
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
    { name = "facility_key", type = "STRING", mode = "REQUIRED" },
    { name = "application_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "loan_amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE" },
    { name = "application_date", type = "DATE", mode = "NULLABLE" },
    { name = "application_status", type = "STRING", mode = "NULLABLE" },
    { name = "event_type", type = "STRING", mode = "NULLABLE" },
    { name = "account_type", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = local.common_labels

  lifecycle { ignore_changes = [schema] }
}

# ============================================================================
# BIGQUERY TABLES - JOB CONTROL
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
    { name = "run_id", type = "STRING", mode = "REQUIRED", description = "Unique pipeline run ID" },
    { name = "system_id", type = "STRING", mode = "REQUIRED", description = "System (generic)" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED", description = "Entity (customers, accounts, etc.)" },
    { name = "extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" },
    { name = "status", type = "STRING", mode = "REQUIRED", description = "PENDING, RUNNING, SUCCESS, FAILED, RETRYING, QUARANTINED" },
    { name = "started_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Job start time" },
    { name = "completed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Job completion time" },
    { name = "failed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Job failure time" },
    { name = "source_files", type = "STRING", mode = "REPEATED", description = "Source file paths" },
    { name = "total_records", type = "INTEGER", mode = "NULLABLE", description = "Total records processed" },
    { name = "error_code", type = "STRING", mode = "NULLABLE", description = "Error code if failed" },
    { name = "error_message", type = "STRING", mode = "NULLABLE", description = "Error message if failed" },
    { name = "error_file_path", type = "STRING", mode = "NULLABLE", description = "Error file path" },
    { name = "failure_stage", type = "STRING", mode = "NULLABLE", description = "Stage where failure occurred" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Record creation time" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Last update time" }
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
    field = "event_timestamp"
  }

  schema = jsonencode([
    { name = "audit_id", type = "STRING", mode = "REQUIRED" },
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "system_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED" },
    { name = "event_type", type = "STRING", mode = "REQUIRED" },
    { name = "event_timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "details", type = "JSON", mode = "NULLABLE" }
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
