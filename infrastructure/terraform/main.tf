# =============================================================================
# GCP Pipeline Reference — Terraform Root Configuration (Generic System)
# =============================================================================
#
# This is the complete infrastructure for the Generic data pipeline:
#   - GCS buckets (landing, archive, error, temp)
#   - BigQuery datasets (ODP, FDP, job_control)
#   - Pub/Sub (file notifications + dead letter)
#   - Cloud Composer (Airflow orchestration)
#   - Service accounts (dataflow, dbt, composer)
#   - IAM bindings (least-privilege per service account)
#   - Entity folder scaffolding in landing bucket
#
# Usage:
#   cd infrastructure/terraform
#   terraform init
#   terraform plan -var="gcp_project_id=<your-project>"
#   terraform apply -var="gcp_project_id=<your-project>"
#
# Destroy:
#   terraform destroy -var="gcp_project_id=<your-project>" -var="force_destroy=true"
# =============================================================================

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
    prefix = "generic/int"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = "europe-west2"
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = "europe-west2"
}

# =============================================================================
# LOCAL VARIABLES
# =============================================================================

locals {
  environment = "int"
  project_id  = var.gcp_project_id
  region      = "europe-west2"
  system_id   = "generic"
  prefix      = "generic-int"

  # Entities that need landing bucket folders
  entities = ["customers", "accounts", "decision", "applications"]

  common_labels = {
    project     = "gcp-pipeline-builder"
    system      = "generic"
    environment = local.environment
    managed_by  = "terraform"
  }
}

# =============================================================================
# GCS BUCKETS
# =============================================================================

resource "google_storage_bucket" "landing" {
  name          = "${local.project_id}-${local.prefix}-landing"
  location      = local.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 90 }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = local.common_labels
}

resource "google_storage_bucket" "archive" {
  name          = "${local.project_id}-${local.prefix}-archive"
  location      = local.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 365 }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition { age = 1825 }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = local.common_labels
}

resource "google_storage_bucket" "error" {
  name          = "${local.project_id}-${local.prefix}-error"
  location      = local.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }

  labels = local.common_labels
}

resource "google_storage_bucket" "temp" {
  name          = "${local.project_id}-${local.prefix}-temp"
  location      = local.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }

  labels = local.common_labels
}

# =============================================================================
# ENTITY FOLDER SCAFFOLDING
# =============================================================================
# Create placeholder .keep files so entity folders exist in the landing bucket.
# File notifications use these paths: generic/<entity>/*.ok

resource "google_storage_bucket_object" "entity_folders" {
  for_each = toset(local.entities)

  name    = "generic/${each.value}/.keep"
  content = " "
  bucket  = google_storage_bucket.landing.name
}

# =============================================================================
# PUB/SUB — FILE NOTIFICATIONS
# =============================================================================

resource "google_pubsub_topic" "generic_file_notifications" {
  name   = "generic-file-notifications"
  labels = local.common_labels
}

resource "google_pubsub_topic" "generic_dead_letter" {
  name   = "generic-file-notifications-dead-letter"
  labels = local.common_labels
}

resource "google_pubsub_subscription" "generic_file_notifications_sub" {
  name  = "generic-file-notifications-sub"
  topic = google_pubsub_topic.generic_file_notifications.name

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.generic_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# Allow GCS to publish notifications to the topic
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.generic_file_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

data "google_storage_project_service_account" "gcs_account" {
  project = var.gcp_project_id
}

# GCS → Pub/Sub notification (triggers on .ok file upload)
resource "google_storage_notification" "generic_file_notification" {
  bucket             = google_storage_bucket.landing.name
  payload_format     = "JSON_API_V1"
  topic              = google_pubsub_topic.generic_file_notifications.id
  event_types        = ["OBJECT_FINALIZE"]
  object_name_prefix = "generic/"
  depends_on         = [google_pubsub_topic_iam_member.gcs_publisher]
}

# =============================================================================
# BIGQUERY DATASETS (ODP / FDP / JOB CONTROL)
# =============================================================================

resource "google_bigquery_dataset" "odp_generic" {
  dataset_id                 = "odp_generic"
  friendly_name              = "ODP Generic - Original Data Product"
  description                = "Raw 1:1 mapping from Generic mainframe extracts (customers, accounts, decision, applications)"
  location                   = "europe-west2"
  delete_contents_on_destroy = true
  labels                     = local.common_labels

  lifecycle {
    ignore_changes = [location]
  }
}

resource "google_bigquery_dataset" "fdp_generic" {
  dataset_id                 = "fdp_generic"
  friendly_name              = "FDP Generic - Foundation Data Product"
  description                = "Transformed Generic data (event_transaction_excess, portfolio_account_excess, portfolio_account_facility)"
  location                   = "europe-west2"
  delete_contents_on_destroy = true
  labels                     = local.common_labels

  lifecycle {
    ignore_changes = [location]
  }
}

resource "google_bigquery_dataset" "job_control" {
  dataset_id                 = "job_control"
  friendly_name              = "Pipeline Job Control"
  description                = "Job tracking, audit trail, and status for all pipelines"
  location                   = "europe-west2"
  delete_contents_on_destroy = true
  labels                     = local.common_labels

  lifecycle {
    ignore_changes = [location]
  }
}

# =============================================================================
# SERVICE ACCOUNTS
# =============================================================================

resource "google_service_account" "generic_dataflow" {
  account_id   = "generic-int-dataflow"
  display_name = "Generic Dataflow Service Account"
  description  = "Service account for Generic Dataflow pipeline execution"
}

resource "google_service_account" "generic_dbt" {
  account_id   = "generic-int-dbt"
  display_name = "Generic dbt Service Account"
  description  = "Service account for Generic dbt transformations"
}

resource "google_service_account" "generic_composer" {
  account_id   = "generic-composer-sa"
  display_name = "Generic Cloud Composer Service Account"
  description  = "Service account for Cloud Composer (Airflow) orchestration"
}

# =============================================================================
# IAM — DATAFLOW SERVICE ACCOUNT
# =============================================================================

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

# =============================================================================
# IAM — DBT SERVICE ACCOUNT
# =============================================================================

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

# =============================================================================
# IAM — COMPOSER SERVICE ACCOUNT
# =============================================================================

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

resource "google_project_iam_member" "generic_composer_storage" {
  project = var.gcp_project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_project_iam_member" "generic_composer_bigquery" {
  project = var.gcp_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.generic_composer.email}"
}

resource "google_pubsub_subscription_iam_member" "generic_composer_subscriber" {
  subscription = google_pubsub_subscription.generic_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.generic_composer.email}"
}

# =============================================================================
# CLOUD COMPOSER (AIRFLOW ORCHESTRATION)
# =============================================================================

resource "google_composer_environment" "generic_composer" {
  name    = "${local.prefix}-composer"
  region  = local.region
  labels  = local.common_labels

  config {
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    software_config {
      image_version = "composer-2-airflow-2"

      pypi_packages = {
        gcp-pipeline-framework = ">=1.0.6"
      }

      env_variables = {
        SYSTEM_ID      = upper(local.system_id)
        GCP_PROJECT_ID = local.project_id
        ENVIRONMENT    = local.environment
      }
    }

    node_config {
      service_account = google_service_account.generic_composer.email
    }
  }

  depends_on = [
    google_project_iam_member.generic_composer_worker,
    google_project_iam_member.generic_composer_dataflow,
    google_project_iam_member.generic_composer_storage,
    google_project_iam_member.generic_composer_bigquery,
  ]
}
