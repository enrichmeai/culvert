 # LOA (Application B Application) - Terraform Main Configuration
#
# Provisions complete GCP infrastructure for LOA pipeline:
# - GCS buckets (landing, archive, error)
# - BigQuery datasets (odp_loa, fdp_loa)
# - Pub/Sub topics and subscriptions
# - Service accounts and IAM roles
#
# LOA System Overview:
# - 1 source entity: Applications
# - 1 ODP table: odp_loa.applications
# - 2 FDP tables: fdp_loa.event_transaction_excess, fdp_loa.portfolio_account_excess
# - No dependency wait: Immediate trigger after ODP load
# - Transformation: SPLIT 1 source → 2 targets

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
    prefix = "loa/staging"
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
  system_id   = "loa"

  # Resource naming convention
  prefix = "loa-${local.environment}"

  common_labels = {
    project     = "gdw-data-migration"
    system      = "loa"
    environment = local.environment
    managed_by  = "terraform"
  }

  # LOA entity configuration (single entity)
  loa_entities = ["applications"]
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Landing bucket for incoming LOA files
resource "google_storage_bucket" "landing" {
  name          = "${var.gcp_project_id}-${local.prefix}-landing"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  # CMEK encryption using shared security key
  encryption {
    default_kms_key_name = var.storage_kms_key_id
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

# Archive bucket for processed LOA files
resource "google_storage_bucket" "archive" {
  name          = "${var.gcp_project_id}-${local.prefix}-archive"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  encryption {
    default_kms_key_name = var.storage_kms_key_id
  }

  # Move to archive after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = local.common_labels
}

# Error bucket for failed LOA files
resource "google_storage_bucket" "error" {
  name          = "${var.gcp_project_id}-${local.prefix}-error"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = var.storage_kms_key_id
  }

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

# Topic for LOA file landing notifications
resource "google_pubsub_topic" "loa_file_notifications" {
  name = "loa-file-notifications"

  # CMEK encryption
  kms_key_name = var.messaging_kms_key_id

  labels = local.common_labels
}

# Subscription for LOA file notifications
resource "google_pubsub_subscription" "loa_file_notifications_sub" {
  name  = "loa-file-notifications-sub"
  topic = google_pubsub_topic.loa_file_notifications.name

  ack_deadline_seconds = 60

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.loa_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "loa_dead_letter" {
  name = "loa-file-notifications-dead-letter"

  kms_key_name = var.messaging_kms_key_id

  labels = local.common_labels
}

# GCS notification to Pub/Sub (triggers on .ok file upload)
resource "google_storage_notification" "loa_file_notification" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.loa_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]

  # Only notify for .ok files (trigger files)
  object_name_prefix = "loa/"

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# Allow GCS to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.loa_file_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# Get GCS service account
data "google_storage_project_service_account" "gcs_account" {
  project = var.gcp_project_id
}

# ============================================================================
# BIGQUERY - DATASETS
# ============================================================================

# ODP Dataset - Original Data Product (raw 1:1 copy)
resource "google_bigquery_dataset" "odp_loa" {
  dataset_id    = "odp_loa"
  friendly_name = "LOA Original Data Product"
  description   = "Raw 1:1 copy of LOA mainframe data - Applications entity"
  location      = var.gcp_region

  default_encryption_configuration {
    kms_key_name = var.bigquery_kms_key_id
  }

  # Default table expiration: none (keep indefinitely)
  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# FDP Dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_loa" {
  dataset_id    = "fdp_loa"
  friendly_name = "LOA Foundation Data Product"
  description   = "Transformed LOA data - event_transaction_excess and portfolio_account_excess tables"
  location      = var.gcp_region

  default_encryption_configuration {
    kms_key_name = var.bigquery_kms_key_id
  }

  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY - ODP TABLES
# ============================================================================

# ODP Applications table
resource "google_bigquery_table" "odp_applications" {
  dataset_id          = google_bigquery_dataset.odp_loa.dataset_id
  table_id            = "applications"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["application_id"]

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Unique application identifier" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Customer identifier" },
    { name = "ssn", type = "STRING", mode = "NULLABLE", description = "Social Security Number (masked)" },
    { name = "loan_amount", type = "NUMERIC", mode = "REQUIRED", description = "Requested loan amount" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE", description = "Interest rate" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE", description = "Loan term in months" },
    { name = "application_date", type = "DATE", mode = "REQUIRED", description = "Application submission date" },
    { name = "application_status", type = "STRING", mode = "REQUIRED", description = "Current application status" },
    { name = "branch_code", type = "STRING", mode = "NULLABLE", description = "Branch code" },
    { name = "product_type", type = "STRING", mode = "NULLABLE", description = "Loan product type" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "REQUIRED", description = "Source file name" },
    { name = "_processed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR record" },
  ])

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY - FDP TABLES (Split transformation: 1 source → 2 targets)
# ============================================================================

# FDP Event Transaction Excess table
resource "google_bigquery_table" "fdp_event_transaction_excess" {
  dataset_id          = google_bigquery_dataset.fdp_loa.dataset_id
  table_id            = "event_transaction_excess"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "event_date"
  }

  clustering = ["application_id", "event_type"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED", description = "Unique event identifier" },
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Source application ID" },
    { name = "event_type", type = "STRING", mode = "REQUIRED", description = "Type of event" },
    { name = "event_date", type = "DATE", mode = "REQUIRED", description = "Event date" },
    { name = "transaction_amount", type = "NUMERIC", mode = "NULLABLE", description = "Transaction amount" },
    { name = "excess_amount", type = "NUMERIC", mode = "NULLABLE", description = "Excess amount" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_application_id", type = "STRING", mode = "REQUIRED", description = "Source application ID" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
  ])

  labels = local.common_labels
}

# FDP Portfolio Account Excess table
resource "google_bigquery_table" "fdp_portfolio_account_excess" {
  dataset_id          = google_bigquery_dataset.fdp_loa.dataset_id
  table_id            = "portfolio_account_excess"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "reporting_date"
  }

  clustering = ["portfolio_id", "account_type"]

  schema = jsonencode([
    { name = "portfolio_id", type = "STRING", mode = "REQUIRED", description = "Portfolio identifier" },
    { name = "account_type", type = "STRING", mode = "REQUIRED", description = "Account type" },
    { name = "reporting_date", type = "DATE", mode = "REQUIRED", description = "Reporting date" },
    { name = "total_excess", type = "NUMERIC", mode = "NULLABLE", description = "Total excess amount" },
    { name = "application_count", type = "INTEGER", mode = "NULLABLE", description = "Number of applications" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
  ])

  labels = local.common_labels
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# LOA Pipeline service account
resource "google_service_account" "loa_pipeline" {
  account_id   = "loa-pipeline-sa"
  display_name = "LOA Pipeline Service Account"
  description  = "Service account for LOA data migration pipeline"
  project      = var.gcp_project_id
}

# ============================================================================
# IAM BINDINGS
# ============================================================================

# Grant pipeline SA access to landing bucket
resource "google_storage_bucket_iam_member" "pipeline_landing_reader" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA access to archive bucket
resource "google_storage_bucket_iam_member" "pipeline_archive_writer" {
  bucket = google_storage_bucket.archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA access to error bucket
resource "google_storage_bucket_iam_member" "pipeline_error_writer" {
  bucket = google_storage_bucket.error.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA BigQuery Data Editor on ODP dataset
resource "google_bigquery_dataset_iam_member" "pipeline_odp_editor" {
  dataset_id = google_bigquery_dataset.odp_loa.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA BigQuery Data Editor on FDP dataset
resource "google_bigquery_dataset_iam_member" "pipeline_fdp_editor" {
  dataset_id = google_bigquery_dataset.fdp_loa.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA Pub/Sub Subscriber
resource "google_pubsub_subscription_iam_member" "pipeline_subscriber" {
  subscription = google_pubsub_subscription.loa_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# Grant pipeline SA Dataflow Worker
resource "google_project_iam_member" "pipeline_dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.loa_pipeline.email}"
}

# ============================================================================
# CLOUD COMPOSER (APACHE AIRFLOW)
# ============================================================================

# Cloud Composer Environment for LOA orchestration
resource "google_composer_environment" "loa_composer" {
  name   = "${local.prefix}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = "composer-2.16.1-airflow-2.10.5"

      env_variables = {
        GCP_PROJECT_ID     = var.gcp_project_id
        LOA_LANDING_BUCKET = google_storage_bucket.landing.name
        LOA_ARCHIVE_BUCKET = google_storage_bucket.archive.name
        LOA_ERROR_BUCKET   = google_storage_bucket.error.name
        ODP_DATASET        = google_bigquery_dataset.odp_loa.dataset_id
        FDP_DATASET        = google_bigquery_dataset.fdp_loa.dataset_id
      }

      pypi_packages = {
        "gcp-pipeline-builder" = ">=1.0.0"
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
      service_account = google_service_account.loa_composer.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.loa_composer_worker,
  ]
}

# Service account for Cloud Composer
resource "google_service_account" "loa_composer" {
  account_id   = "loa-composer-sa"
  display_name = "LOA Cloud Composer Service Account"
}

# Composer service account IAM roles
resource "google_project_iam_member" "loa_composer_worker" {
  project = var.gcp_project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.loa_composer.email}"
}

resource "google_project_iam_member" "loa_composer_dataflow" {
  project = var.gcp_project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.loa_composer.email}"
}

resource "google_project_iam_member" "loa_composer_bigquery" {
  project = var.gcp_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.loa_composer.email}"
}

resource "google_project_iam_member" "loa_composer_storage" {
  project = var.gcp_project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.loa_composer.email}"
}

resource "google_pubsub_subscription_iam_member" "loa_composer_subscriber" {
  subscription = google_pubsub_subscription.loa_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.loa_composer.email}"
}

