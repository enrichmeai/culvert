# GCP Infrastructure for Legacy Migration Platform
# Terraform Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "legacy-migration-reference-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Local variables
locals {
  services = [
    "bigquery.googleapis.com",
    "dataflow.googleapis.com",
    "composer.googleapis.com",
    "run.googleapis.com",
    "container.googleapis.com",
    "spanner.googleapis.com",
    "apigee.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
  ]
}

# Enable required APIs
resource "google_project_service" "services" {
  for_each = toset(local.services)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

# BigQuery Dataset
resource "google_bigquery_dataset" "customer_data" {
  dataset_id    = "customer_data"
  friendly_name = "Customer Data"
  description   = "Customer data migrated from legacy Teradata"
  location      = var.region

  default_table_expiration_ms = null

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    source      = "legacy-migration-reference"
  }

  depends_on = [google_project_service.services]
}

# Cloud Storage buckets
resource "google_storage_bucket" "data_bucket" {
  name          = "${var.project_id}-data"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_storage_bucket" "dataflow_temp" {
  name          = "${var.project_id}-dataflow-temp"
  location      = var.region
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

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Cloud Spanner Instance
resource "google_spanner_instance" "customer_db" {
  name             = "customer-db-${var.environment}"
  config           = "regional-${var.region}"
  display_name     = "Customer Database"
  processing_units = var.spanner_processing_units

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.services]
}

resource "google_spanner_database" "customers" {
  instance = google_spanner_instance.customer_db.name
  name     = "customers"

  ddl = [
    <<-EOT
      CREATE TABLE Customers (
        customer_id STRING(36) NOT NULL,
        customer_name STRING(100) NOT NULL,
        email STRING(150),
        phone STRING(20),
        address STRING(200),
        customer_type STRING(20) NOT NULL,
        status STRING(20) NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
      ) PRIMARY KEY (customer_id)
    EOT
  ]

  deletion_protection = var.environment == "prod"
}

# Pub/Sub Topics for event streaming
resource "google_pubsub_topic" "customer_events" {
  name = "customer-events"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_pubsub_subscription" "customer_events_sub" {
  name  = "customer-events-subscription"
  topic = google_pubsub_topic.customer_events.name

  ack_deadline_seconds = 20

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = ""
  }
}

# Service Account for Cloud Run services
resource "google_service_account" "cloud_run_sa" {
  account_id   = "cloud-run-services"
  display_name = "Cloud Run Services Service Account"
  description  = "Service account for Cloud Run microservices"
}

# IAM bindings
resource "google_project_iam_member" "cloud_run_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloud_run_spanner" {
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloud_run_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Cloud Run service for customer microservice
resource "google_cloud_run_service" "customer_service" {
  name     = "customer-service"
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.cloud_run_sa.email

      containers {
        image = "gcr.io/${var.project_id}/customer-service:latest"

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "BQ_DATASET_ID"
          value = google_bigquery_dataset.customer_data.dataset_id
        }

        env {
          name  = "SPANNER_INSTANCE_ID"
          value = google_spanner_instance.customer_db.name
        }

        env {
          name  = "SPANNER_DATABASE_ID"
          value = google_spanner_database.customers.name
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "100"
        "autoscaling.knative.dev/minScale" = "1"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.services]
}

# Allow unauthenticated access (ONLY FOR DEV - REMOVE IN PRODUCTION)
# For production, use IAM roles and service accounts
resource "google_cloud_run_service_iam_member" "public_access" {
  count = var.environment == "dev" ? 1 : 0

  service  = google_cloud_run_service.customer_service.name
  location = google_cloud_run_service.customer_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Monitoring - Alert Policy
resource "google_monitoring_alert_policy" "customer_service_error_rate" {
  display_name = "Customer Service High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Error rate above threshold"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"customer-service\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 10

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channels

  alert_strategy {
    auto_close = "86400s"
  }
}

# Outputs
output "bigquery_dataset_id" {
  value = google_bigquery_dataset.customer_data.dataset_id
}

output "spanner_instance_name" {
  value = google_spanner_instance.customer_db.name
}

output "customer_service_url" {
  value = google_cloud_run_service.customer_service.status[0].url
}

output "data_bucket_name" {
  value = google_storage_bucket.data_bucket.name
}
