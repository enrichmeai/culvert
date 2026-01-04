# EM (Application A) - Terraform Main Configuration
#
# Provisions complete GCP infrastructure for EM pipeline:
# - GCS buckets (landing, archive, error)
# - BigQuery datasets (odp_em, fdp_em, job_control)
# - Pub/Sub topics and subscriptions
# - Service accounts and IAM roles
#
# EM System Overview:
# - 3 source entities: Customers, Accounts, Decision
# - 3 ODP tables: odp_em.customers, odp_em.accounts, odp_em.decision
# - 1 FDP table: fdp_em.em_attributes (JOIN of 3 sources)
# - Dependency wait: All 3 entities must be loaded before FDP transformation

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
    bucket = "gdw-terraform-state"
    prefix = "em/staging"
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
  system_id   = "em"

  # Resource naming convention
  prefix = "em-${local.environment}"

  common_labels = {
    project     = "gdw-data-migration"
    system      = "em"
    environment = local.environment
    managed_by  = "terraform"
  }

  # EM entity configuration
  em_entities = ["customers", "accounts", "decision"]
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Landing bucket for incoming EM files
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
  for_each = toset(local.em_entities)

  name    = "em/${each.value}/.keep"
  content = "# Placeholder for ${each.value} entity files"
  bucket  = google_storage_bucket.landing.name
}

# Archive bucket for processed EM files
resource "google_storage_bucket" "archive" {
  name          = "${var.gcp_project_id}-${local.prefix}-archive"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = true  # Always version archives
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

# Error bucket for failed EM files
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

# ============================================================================
# PUB/SUB - FILE NOTIFICATIONS
# ============================================================================

# Topic for EM file landing notifications
resource "google_pubsub_topic" "em_file_notifications" {
  name = "em-file-notifications"

  labels = local.common_labels
}

# Subscription for EM file notifications
resource "google_pubsub_subscription" "em_file_notifications_sub" {
  name  = "em-file-notifications-sub"
  topic = google_pubsub_topic.em_file_notifications.name

  ack_deadline_seconds = 60

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.em_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "em_dead_letter" {
  name = "em-file-notifications-dead-letter"

  labels = local.common_labels
}

# GCS notification to Pub/Sub (triggers on .ok file upload)
resource "google_storage_notification" "em_file_notification" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.em_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]

  # Only notify for .ok files (trigger files)
  object_name_prefix = "em/"

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# Allow GCS to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.em_file_notifications.name
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
resource "google_bigquery_dataset" "odp_em" {
  dataset_id    = "odp_em"
  friendly_name = "ODP EM - Original Data Product"
  description   = "Raw data from EM mainframe extracts (customers, accounts, decision)"
  location      = var.bq_location

  labels = local.common_labels
}

# FDP dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_em" {
  dataset_id    = "fdp_em"
  friendly_name = "FDP EM - Foundation Data Product"
  description   = "Transformed EM data (em_attributes - join of 3 sources)"
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
# BIGQUERY TABLES - ODP (Customers, Accounts, Decision)
# ============================================================================

# ODP: Customers table
resource "google_bigquery_table" "odp_customers" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "customers"

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
}

# ODP: Customers errors table
resource "google_bigquery_table" "odp_customers_errors" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "customers_errors"

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
}

# ODP: Accounts table
resource "google_bigquery_table" "odp_accounts" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "accounts"

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
}

# ODP: Accounts errors table
resource "google_bigquery_table" "odp_accounts_errors" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "accounts_errors"

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
}

# ODP: Decision table
resource "google_bigquery_table" "odp_decision" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "decision"

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
}

# ODP: Decision errors table
resource "google_bigquery_table" "odp_decision_errors" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = "decision_errors"

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
}

# ============================================================================
# BIGQUERY TABLES - FDP (em_attributes - JOIN of 3 sources)
# ============================================================================

resource "google_bigquery_table" "fdp_em_attributes" {
  dataset_id = google_bigquery_dataset.fdp_em.dataset_id
  table_id   = "em_attributes"

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "account_id"]

  schema = jsonencode([
    # Primary key
    { name = "attribute_key", type = "STRING", mode = "REQUIRED", description = "Composite primary key" },

    # Customer attributes
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Customer ID" },
    { name = "ssn_masked", type = "STRING", mode = "NULLABLE", description = "Masked SSN (PII)" },
    { name = "first_name", type = "STRING", mode = "NULLABLE", description = "First name" },
    { name = "last_name", type = "STRING", mode = "NULLABLE", description = "Last name" },
    { name = "date_of_birth", type = "DATE", mode = "NULLABLE", description = "Date of birth" },
    { name = "customer_status", type = "STRING", mode = "NULLABLE", description = "Customer status" },

    # Account attributes
    { name = "account_id", type = "STRING", mode = "NULLABLE", description = "Account ID" },
    { name = "account_type_desc", type = "STRING", mode = "NULLABLE", description = "Account type description" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE", description = "Current balance" },
    { name = "account_open_date", type = "DATE", mode = "NULLABLE", description = "Account open date" },

    # Decision attributes
    { name = "decision_id", type = "STRING", mode = "NULLABLE", description = "Decision ID" },
    { name = "decision_outcome", type = "STRING", mode = "NULLABLE", description = "Decision outcome" },
    { name = "decision_date", type = "DATE", mode = "NULLABLE", description = "Decision date" },
    { name = "decision_reason", type = "STRING", mode = "NULLABLE", description = "Decision reason" },

    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Transformation timestamp" }
  ])

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY TABLES - JOB CONTROL
# ============================================================================

resource "google_bigquery_table" "pipeline_jobs" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  table_id   = "pipeline_jobs"

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["system_id", "entity_type", "status"]

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED", description = "Unique pipeline run ID" },
    { name = "system_id", type = "STRING", mode = "REQUIRED", description = "System (em, loa)" },
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
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# Dataflow service account for EM pipelines
resource "google_service_account" "em_dataflow" {
  account_id   = "${local.prefix}-dataflow"
  display_name = "EM Dataflow Service Account"
  description  = "Service account for EM Dataflow pipeline execution"
}

# dbt service account for EM transformations
resource "google_service_account" "em_dbt" {
  account_id   = "${local.prefix}-dbt"
  display_name = "EM dbt Service Account"
  description  = "Service account for EM dbt transformations"
}

# ============================================================================
# IAM ROLES & PERMISSIONS
# ============================================================================

# Dataflow worker role
resource "google_project_iam_member" "em_dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.em_dataflow.email}"
}

# Dataflow - GCS permissions
resource "google_storage_bucket_iam_member" "em_dataflow_landing" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.em_dataflow.email}"
}

resource "google_storage_bucket_iam_member" "em_dataflow_archive" {
  bucket = google_storage_bucket.archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.em_dataflow.email}"
}

resource "google_storage_bucket_iam_member" "em_dataflow_error" {
  bucket = google_storage_bucket.error.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.em_dataflow.email}"
}

# Dataflow - BigQuery ODP permissions
resource "google_bigquery_dataset_iam_member" "em_dataflow_odp" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.em_dataflow.email}"
}

# Dataflow - Job control permissions
resource "google_bigquery_dataset_iam_member" "em_dataflow_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.em_dataflow.email}"
}

# Dataflow - Pub/Sub subscriber
resource "google_pubsub_subscription_iam_member" "em_dataflow_subscriber" {
  subscription = google_pubsub_subscription.em_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.em_dataflow.email}"
}

# dbt - BigQuery permissions
resource "google_bigquery_dataset_iam_member" "em_dbt_odp_reader" {
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.em_dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "em_dbt_fdp_editor" {
  dataset_id = google_bigquery_dataset.fdp_em.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.em_dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "em_dbt_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.em_dbt.email}"
}

# ============================================================================
# CLOUD COMPOSER (APACHE AIRFLOW)
# ============================================================================

# Cloud Composer Environment for EM orchestration
resource "google_composer_environment" "em_composer" {
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
        ODP_DATASET       = google_bigquery_dataset.odp_em.dataset_id
        FDP_DATASET       = google_bigquery_dataset.fdp_em.dataset_id
        JOB_CONTROL_TABLE = "${google_bigquery_dataset.job_control.dataset_id}.pipeline_jobs"
      }

      # PyPI packages will be installed via requirements.txt in DAGs
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
      service_account = google_service_account.em_composer.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.em_composer_worker,
  ]
}

# Service account for Cloud Composer
resource "google_service_account" "em_composer" {
  account_id   = "em-composer-sa"
  display_name = "EM Cloud Composer Service Account"
}

# Composer service account IAM roles
resource "google_project_iam_member" "em_composer_worker" {
  project = var.gcp_project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.em_composer.email}"
}

resource "google_project_iam_member" "em_composer_dataflow" {
  project = var.gcp_project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.em_composer.email}"
}

resource "google_project_iam_member" "em_composer_bigquery" {
  project = var.gcp_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.em_composer.email}"
}

resource "google_project_iam_member" "em_composer_storage" {
  project = var.gcp_project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.em_composer.email}"
}

resource "google_pubsub_subscription_iam_member" "em_composer_subscriber" {
  subscription = google_pubsub_subscription.em_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.em_composer.email}"
}

