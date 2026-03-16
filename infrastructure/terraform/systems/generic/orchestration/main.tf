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
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "first_name", type = "STRING", mode = "NULLABLE", description = "First name" },
    { name = "last_name", type = "STRING", mode = "NULLABLE", description = "Last name" },
    { name = "account_id", type = "STRING", mode = "REQUIRED", description = "Account ID" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE", description = "Current balance" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date" }
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
    { name = "decision_id", type = "STRING", mode = "REQUIRED", description = "Decision ID" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Customer ID" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED", description = "Decision code" },
    { name = "score", type = "INTEGER", mode = "NULLABLE", description = "Credit score" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date" }
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
    { name = "system_id", type = "STRING", mode = "REQUIRED", description = "System (generic, generic)" },
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
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Last update time" },
    { name = "job_type", type = "STRING", mode = "NULLABLE", description = "ODP_INGESTION, FDP_TRANSFORMATION, CDP_TRANSFORMATION" },
    { name = "retry_count", type = "INTEGER", mode = "NULLABLE", description = "Number of retry attempts" },
    { name = "max_retries", type = "INTEGER", mode = "NULLABLE", description = "Configured maximum retries" },
    { name = "parent_run_ids", type = "STRING", mode = "REPEATED", description = "Source ODP job run_ids for FDP lineage" },
    { name = "dbt_model_name", type = "STRING", mode = "NULLABLE", description = "dbt model name for FDP/CDP jobs" }
  ])

  labels = local.common_labels
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

# ============================================================================
# IAM ROLES & PERMISSIONS
# ============================================================================

# Dataflow worker role
resource "google_project_iam_member" "generic_dataflow_worker" {
  project = var.gcp_project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

# Dataflow - GCS permissions
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

# Dataflow - BigQuery ODP permissions
resource "google_bigquery_dataset_iam_member" "generic_dataflow_odp" {
  dataset_id = google_bigquery_dataset.odp_generic.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

# Dataflow - Job control permissions
resource "google_bigquery_dataset_iam_member" "generic_dataflow_job_control" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

# Dataflow - Pub/Sub subscriber
resource "google_pubsub_subscription_iam_member" "generic_dataflow_subscriber" {
  subscription = google_pubsub_subscription.generic_file_notifications_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.generic_dataflow.email}"
}

# dbt - BigQuery permissions
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
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}

# ============================================================================
# CLOUD COMPOSER (APACHE AIRFLOW)
# ============================================================================

# Cloud Composer Environment for Generic orchestration
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
      service_account = google_service_account.generic_composer.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.generic_composer_worker,
  ]
}

# Service account for Cloud Composer
resource "google_service_account" "generic_composer" {
  account_id   = "generic-composer-sa"
  display_name = "Generic Cloud Composer Service Account"
}

# Composer service account IAM roles
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

