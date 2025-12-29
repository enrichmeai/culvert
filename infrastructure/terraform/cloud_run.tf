# LOA Blueprint - Cloud Run Services Configuration
#
# Provisions Cloud Run services for:
# - API endpoints
# - Data validation services
# - Monitoring and alerting

# ============================================================================
# CLOUD RUN SERVICES
# ============================================================================

# Validation API Service
resource "google_cloud_run_service" "validation_api" {
  name     = "${local.prefix}-validation-api"
  location = var.gcp_region

  template {
    spec {
      service_account_name = google_service_account.cloud_run.email

      containers {
        image = var.validation_api_image != "" ? var.validation_api_image : "gcr.io/${var.gcp_project_id}/loa-validation-api:latest"

        env {
          name  = "GCP_PROJECT_ID"
          value = var.gcp_project_id
        }

        env {
          name  = "BIGQUERY_DATASET_RAW"
          value = google_bigquery_dataset.raw.dataset_id
        }

        env {
          name  = "GCS_BUCKET_INPUT"
          value = google_storage_bucket.input.name
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "LOG_LEVEL"
          value = var.log_level
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
          requests = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        liveness_probe {
          http_get {
            path = "/health"
          }
          initial_delay_seconds = 10
          timeout_seconds       = 5
        }

        startup_probe {
          http_get {
            path = "/ready"
          }
          initial_delay_seconds = 5
          timeout_seconds       = 3
          failure_threshold     = 3
        }
      }

      timeout_seconds = 300

      max_instances = 100
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "100"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true

  depends_on = [
    google_project_iam_member.cloud_run_sa_user,
    google_bigquery_dataset.raw
  ]
}

# Make service publicly accessible
resource "google_cloud_run_iam_member" "validation_api_public" {
  service  = google_cloud_run_service.validation_api.name
  location = google_cloud_run_service.validation_api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Data Quality API Service
resource "google_cloud_run_service" "data_quality_api" {
  name     = "${local.prefix}-data-quality-api"
  location = var.gcp_region

  template {
    spec {
      service_account_name = google_service_account.cloud_run.email

      containers {
        image = var.data_quality_image != "" ? var.data_quality_image : "gcr.io/${var.gcp_project_id}/loa-data-quality-api:latest"

        env {
          name  = "GCP_PROJECT_ID"
          value = var.gcp_project_id
        }

        env {
          name  = "BIGQUERY_DATASET_RAW"
          value = google_bigquery_dataset.raw.dataset_id
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        liveness_probe {
          http_get {
            path = "/health"
          }
          initial_delay_seconds = 10
        }
      }

      max_instances = 50
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "0"
        "autoscaling.knative.dev/maxScale" = "50"
      }
    }
  }

  autogenerate_revision_name = true

  depends_on = [
    google_bigquery_dataset.raw
  ]
}

# ============================================================================
# CLOUD RUN CONFIGURATIONS
# ============================================================================

# Environment-based secret management
resource "google_secret_manager_secret" "validation_api_key" {
  secret_id = "${local.prefix}-validation-api-key"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "validation_api_key" {
  secret           = google_secret_manager_secret.validation_api_key.id
  secret_data      = var.validation_api_key
  deletion_policy  = "DELETE"
}

# Service account secret access for Cloud Run
resource "google_secret_manager_iam_member" "cloud_run_secret_accessor" {
  secret_id = google_secret_manager_secret.validation_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ============================================================================
# LOAD BALANCER & TRAFFIC MANAGEMENT
# ============================================================================

# Cloud Load Balancer for API services
resource "google_compute_backend_service" "cloud_run_backend" {
  name = "${local.prefix}-backend"

  protocol = "HTTP2"
  port_name = "h2c"

  backend {
    group           = google_compute_network_endpoint_group.cloud_run_neg.id
    balancing_mode  = "RATE"
    max_rate_per_endpoint = 1000
  }

  health_checks = [google_compute_health_check.cloud_run.id]

  session_affinity = "NONE"

  log_config {
    enable = true
    sample_rate = 0.1
  }
}

# Network Endpoint Group for Cloud Run
resource "google_compute_network_endpoint_group" "cloud_run_neg" {
  name         = "${local.prefix}-cloud-run-neg"
  network_endpoint_type = "SERVERLESS"

  cloud_run_config {
    service = google_cloud_run_service.validation_api.name
  }
  region = var.gcp_region
}

# Health check for Cloud Run
resource "google_compute_health_check" "cloud_run" {
  name = "${local.prefix}-cloud-run-health-check"

  http_health_check {
    port  = "80"
    path  = "/health"
  }

  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3
}

# ============================================================================
# MONITORING & ALERTING
# ============================================================================

# Monitoring alert policy for Cloud Run
resource "google_monitoring_alert_policy" "cloud_run_errors" {
  display_name = "${local.prefix} Cloud Run Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run Error Rate > 5%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${google_cloud_run_service.validation_api.name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channels

  alert_strategy {
    auto_close = "1800s"
  }
}

# Monitoring alert for Cloud Run latency
resource "google_monitoring_alert_policy" "cloud_run_latency" {
  display_name = "${local.prefix} Cloud Run High Latency"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run P95 Latency > 1s"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = 1000  # milliseconds

      aggregations {
        alignment_period    = "60s"
        per_series_aligner  = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = var.notification_channels
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "validation_api_url" {
  value       = google_cloud_run_service.validation_api.status[0].url
  description = "URL of the Validation API"
}

output "data_quality_api_url" {
  value       = google_cloud_run_service.data_quality_api.status[0].url
  description = "URL of the Data Quality API"
}

