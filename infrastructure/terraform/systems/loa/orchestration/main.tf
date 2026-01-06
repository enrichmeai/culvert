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

