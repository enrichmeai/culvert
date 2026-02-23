# Application2 (Application B Application) - Terraform Main Configuration
#
# Provisions complete GCP infrastructure for Application2 pipeline:
# - GCS buckets (landing, archive, error)
# - BigQuery datasets (odp_application2, fdp_application2)
# - Pub/Sub topics and subscriptions
# - Service accounts and IAM roles
#
# Application2 System Overview:
# - 1 source entity: Applications
# - 1 ODP table: odp_application2.applications
# - 1 FDP table: fdp_application2.portfolio_account_facility
# - No dependency wait: Immediate trigger after ODP load
# - Transformation: MAP 1 source → 1 target

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
    prefix = "application2/staging"
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
  system_id   = "application2"

  # Resource naming convention
  prefix = "application2-${local.environment}"

  common_labels = {
    project     = "gcp-pipeline-builder"
    system      = "application2"
    environment = local.environment
    managed_by  = "terraform"
  }

  # Application2 entity configuration (single entity)
  application2_entities = ["applications"]
}

# ============================================================================
# GCS BUCKETS
# ============================================================================

# Landing bucket for incoming Application2 files
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

# Archive bucket for processed Application2 files
resource "google_storage_bucket" "archive" {
  name          = "${var.gcp_project_id}-${local.prefix}-archive"
  location      = var.gcp_region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
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

# Error bucket for failed Application2 files
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

# Topic for Application2 file landing notifications
resource "google_pubsub_topic" "application2_file_notifications" {
  name = "application2-file-notifications"

  # CMEK encryption

  labels = local.common_labels
}

# Subscription for Application2 file notifications
resource "google_pubsub_subscription" "application2_file_notifications_sub" {
  name  = "application2-file-notifications-sub"
  topic = google_pubsub_topic.application2_file_notifications.name

  ack_deadline_seconds = 60

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.application2_dead_letter.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "application2_dead_letter" {
  name = "application2-file-notifications-dead-letter"


  labels = local.common_labels
}

# GCS notification to Pub/Sub (triggers on .ok file upload)
resource "google_storage_notification" "application2_file_notification" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.application2_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]

  # Only notify for .ok files (trigger files)
  object_name_prefix = "application2/"

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# Allow GCS to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.application2_file_notifications.name
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
