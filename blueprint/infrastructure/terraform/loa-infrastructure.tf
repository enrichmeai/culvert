# LOA Blueprint - GCP Infrastructure
# Terraform configuration for LOA migration project
# Best Practice: Separate infrastructure provisioning from application code

terraform {
  required_version = ">= 1.5.0"

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
    # Backend configuration provided via backend config file
    # Use: terraform init -backend-config=environments/dev-backend.tfvars
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local variables
locals {
  services_to_enable = [
    "bigquery.googleapis.com",
    "storage-component.googleapis.com",
    "dataflow.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudfunctions.googleapis.com",
    "composer.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]

  common_labels = {
    project     = "loa-migration"
    environment = var.environment
    managed_by  = "terraform"
    team        = "enterprise-platform"
  }
}

#------------------------------------------------------------------------------
# PROJECT SERVICES
#------------------------------------------------------------------------------

resource "google_project_service" "services" {
  for_each = toset(local.services_to_enable)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

#------------------------------------------------------------------------------
# SERVICE ACCOUNTS (BEST PRACTICE: Separate SA per service)
#------------------------------------------------------------------------------

# Dataflow service account
resource "google_service_account" "dataflow" {
  account_id   = "loa-dataflow-${var.environment}"
  display_name = "LOA Dataflow Service Account (${var.environment})"
  description  = "Service account for LOA Dataflow pipelines"
  project      = var.project_id

  depends_on = [google_project_service.services]
}

# Cloud Function service account
resource "google_service_account" "cloud_function" {
  account_id   = "loa-cf-${var.environment}"
  display_name = "LOA Cloud Function Service Account (${var.environment})"
  description  = "Service account for LOA Cloud Functions"
  project      = var.project_id

  depends_on = [google_project_service.services]
}

# Cloud Composer service account
resource "google_service_account" "composer" {
  count = var.enable_composer ? 1 : 0

  account_id   = "loa-composer-${var.environment}"
  display_name = "LOA Cloud Composer Service Account (${var.environment})"
  description  = "Service account for LOA Cloud Composer"
  project      = var.project_id

  depends_on = [google_project_service.services]
}

#------------------------------------------------------------------------------
# IAM ROLES (BEST PRACTICE: Least privilege principle)
#------------------------------------------------------------------------------

# Dataflow service account roles
resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

# Cloud Function service account roles
resource "google_project_iam_member" "cf_dataflow" {
  project = var.project_id
  role    = "roles/dataflow.developer"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

resource "google_project_iam_member" "cf_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

#------------------------------------------------------------------------------
# CLOUD STORAGE BUCKETS
#------------------------------------------------------------------------------

# Data bucket (input/processing)
resource "google_storage_bucket" "data" {
  name          = "${var.project_id}-loa-data"
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  versioning {
    enabled = var.environment == "prod"
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.loa_messaging_key.id
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

# Archive bucket
resource "google_storage_bucket" "archive" {
  name          = "${var.project_id}-loa-archive"
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = google_kms_crypto_key.loa_messaging_key.id
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

# Temp bucket for Dataflow
resource "google_storage_bucket" "temp" {
  name          = "${var.project_id}-loa-temp"
  location      = var.region
  project       = var.project_id
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

#------------------------------------------------------------------------------
# BIGQUERY DATASETS AND TABLES
#------------------------------------------------------------------------------

# BigQuery dataset
resource "google_bigquery_dataset" "loa_migration" {
  dataset_id  = "loa_migration"
  location    = var.region
  project     = var.project_id
  description = "LOA migration dataset for ${var.environment}"

  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.loa_messaging_key.id
  }

  default_table_expiration_ms = var.environment == "dev" ? 2592000000 : null # 30 days for dev

  labels = local.common_labels

  access {
    role          = "OWNER"
    user_by_email = google_service_account.dataflow.email
  }

  depends_on = [google_project_service.services]
}

# Applications raw table
resource "google_bigquery_table" "applications_raw" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "applications_raw"
  project    = var.project_id

  description = "Raw loan application data from mainframe (LOAJOB)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["application_date", "loan_type"]

  schema = file("${path.module}/../../components/schemas/applications_raw.json")

  labels = local.common_labels
}

# Applications errors table
resource "google_bigquery_table" "applications_errors" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "applications_errors"
  project    = var.project_id

  description = "Validation errors from applications processing (LOAJOB)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["run_id", "error_field"]

  schema = file("${path.module}/../../components/schemas/applications_errors.json")

  labels = local.common_labels
}

# Customers raw table
resource "google_bigquery_table" "customers_raw" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "customers_raw"
  project    = var.project_id

  description = "Customer master data from mainframe (CUSTNOJOB)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["customer_since", "branch_code"]

  schema = file("${path.module}/../../components/schemas/customers_raw.json")

  labels = local.common_labels
}

# Customers errors table
resource "google_bigquery_table" "customers_errors" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "customers_errors"
  project    = var.project_id

  description = "Validation errors from customers processing (CUSTNOJOB)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["run_id", "error_field"]

  schema = file("${path.module}/../../components/schemas/customers_errors.json")

  labels = local.common_labels
}

# Branches raw table
resource "google_bigquery_table" "branches_raw" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "branches_raw"
  project    = var.project_id

  description = "Branch information from mainframe (BRANCHJOB)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["region", "state"]

  schema = file("${path.module}/../../components/schemas/branches_raw.json")

  labels = local.common_labels
}

# Collateral raw table
resource "google_bigquery_table" "collateral_raw" {
  dataset_id = google_bigquery_dataset.loa_migration.dataset_id
  table_id   = "collateral_raw"
  project    = var.project_id

  description = "Collateral details from mainframe (COLLATERAL)"

  time_partitioning {
    type  = "DAY"
    field = "processed_timestamp"
  }

  clustering = ["collateral_type", "appraisal_date"]

  schema = file("${path.module}/../../components/schemas/collateral_raw.json")

  labels = local.common_labels
}

#------------------------------------------------------------------------------
# PUB/SUB
#------------------------------------------------------------------------------

# Topic for pipeline notifications with CMEK
resource "google_pubsub_topic" "loa_notifications" {
  name         = "loa-processing-notifications"
  project      = var.project_id
  kms_key_name = google_kms_crypto_key.loa_messaging_key.id

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

# Dead-letter topic
resource "google_pubsub_topic" "loa_notifications_dead_letter" {
  name         = "loa-notifications-dead-letter"
  project      = var.project_id
  kms_key_name = google_kms_crypto_key.loa_messaging_key.id

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

# Subscription for notifications
resource "google_pubsub_subscription" "loa_notifications_sub" {
  name  = "loa-processing-notifications-sub"
  topic = google_pubsub_topic.loa_notifications.name

  ack_deadline_seconds = 60
  message_retention_duration = "604800s" # 7 days
  enable_message_ordering = true

  expiration_policy {
    ttl = "2678400s" # 31 days
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.loa_notifications_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# GCS Storage Notification for .ok files
resource "google_storage_notification" "loa_ok_notification" {
  bucket         = google_storage_bucket.data.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.loa_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
  object_name_prefix = "incoming/"

  # Note: object_name_suffix is not directly supported in google_storage_notification
  # We will filter for .ok in the subscriber (Airflow)
}

# IAM permissions for Dataflow to use KMS (CMEK)
resource "google_kms_crypto_key_iam_member" "dataflow_kms" {
  crypto_key_id = google_kms_crypto_key.loa_messaging_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.dataflow.email}"
}

# IAM permissions for Pub/Sub to use KMS
resource "google_pubsub_topic_iam_member" "pubsub_kms_binding" {
  project = var.project_id
  topic   = google_pubsub_topic.loa_notifications.name
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# IAM permissions for GCS to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.loa_notifications.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
}

# IAM permissions for Composer to subscribe
resource "google_pubsub_subscription_iam_member" "composer_subscriber" {
  count = var.enable_composer ? 1 : 0

  subscription = google_pubsub_subscription.loa_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.composer[0].email}"
}

#------------------------------------------------------------------------------
# CLOUD SCHEDULER (Optional)
#------------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "daily_pipeline" {
  count = var.enable_scheduler ? 1 : 0

  name     = "loa-daily-pipeline-${var.environment}"
  project  = var.project_id
  region   = var.region
  schedule = var.pipeline_schedule

  http_target {
    uri         = "https://${var.region}-${var.project_id}.cloudfunctions.net/loa-auto-trigger"
    http_method = "POST"
  }

  depends_on = [google_project_service.services]
}

#------------------------------------------------------------------------------
# OUTPUTS
#------------------------------------------------------------------------------

output "data_bucket" {
  value       = google_storage_bucket.data.name
  description = "Data bucket name"
}

output "archive_bucket" {
  value       = google_storage_bucket.archive.name
  description = "Archive bucket name"
}

output "temp_bucket" {
  value       = google_storage_bucket.temp.name
  description = "Temp bucket name"
}

output "bigquery_dataset" {
  value       = google_bigquery_dataset.loa_migration.dataset_id
  description = "BigQuery dataset ID"
}

output "pubsub_topic" {
  value       = google_pubsub_topic.loa_notifications.name
  description = "Pub/Sub topic name"
}

output "dataflow_service_account" {
  value       = google_service_account.dataflow.email
  description = "Dataflow service account email"
}

output "cloud_function_service_account" {
  value       = google_service_account.cloud_function.email
  description = "Cloud Function service account email"
}

