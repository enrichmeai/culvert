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

