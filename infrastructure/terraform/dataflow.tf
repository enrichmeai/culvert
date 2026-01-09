# LOA Blueprint - Google Dataflow Configuration
#
# Provisions Dataflow resources for:
# - Pipeline job templates
# - Worker configuration
# - Autoscaling policies
# - Network requirements

# ============================================================================
# DATAFLOW JOB TEMPLATES
# ============================================================================

# Applications Processing Pipeline
resource "google_dataflow_job" "applications_pipeline" {
  name              = "${local.prefix}-applications-pipeline"
  template_gcs_path = var.dataflow_template_path_applications
  temp_gcs_location = "gs://${google_storage_bucket.input.name}/dataflow-temp"

  parameters = {
    inputFile       = "gs://${google_storage_bucket.input.name}/applications/*.csv"
    outputTable     = "${var.gcp_project_id}:${google_bigquery_dataset.raw.dataset_id}.applications_raw"
    stagingLocation = "gs://${google_storage_bucket.input.name}/dataflow-staging"
    errorPath       = "gs://${google_storage_bucket.error.name}/applications-errors/"

    # Worker configuration
    workerMachineType = var.dataflow_worker_machine_type
    numWorkers        = var.dataflow_num_workers
    maxWorkers        = var.dataflow_max_workers

    # Autoscaling
    autoscalingAlgorithm = "THROUGHPUT_BASED"
  }

  service_account_email = google_service_account.dataflow.email
  network               = google_compute_network.main.name
  subnetwork            = google_compute_subnetwork.main.id

  machine_type = var.dataflow_worker_machine_type

  skip_wait_on_job_termination = false
  on_delete                    = "cancel"

  depends_on = [
    google_storage_bucket.input,
    google_bigquery_dataset.raw,
    google_service_account.dataflow
  ]
}

# Customers Processing Pipeline
resource "google_dataflow_job" "customers_pipeline" {
  name              = "${local.prefix}-customers-pipeline"
  template_gcs_path = var.dataflow_template_path_customers
  temp_gcs_location = "gs://${google_storage_bucket.input.name}/dataflow-temp"

  parameters = {
    inputFile       = "gs://${google_storage_bucket.input.name}/customers/*.csv"
    outputTable     = "${var.gcp_project_id}:${google_bigquery_dataset.raw.dataset_id}.customers_raw"
    stagingLocation = "gs://${google_storage_bucket.input.name}/dataflow-staging"
    errorPath       = "gs://${google_storage_bucket.error.name}/customers-errors/"

    workerMachineType = var.dataflow_worker_machine_type
    numWorkers        = var.dataflow_num_workers
    maxWorkers        = var.dataflow_max_workers

    autoscalingAlgorithm = "THROUGHPUT_BASED"
  }

  service_account_email = google_service_account.dataflow.email
  network               = google_compute_network.main.name
  subnetwork            = google_compute_subnetwork.main.id

  skip_wait_on_job_termination = false
  on_delete                    = "cancel"

  depends_on = [
    google_storage_bucket.input,
    google_bigquery_dataset.raw,
    google_service_account.dataflow
  ]
}

# ============================================================================
# DATAFLOW FLEX TEMPLATES
# ============================================================================

# Flex template for generic CSV processing
resource "google_dataflow_flex_template_job" "csv_processor" {
  provider                = google-beta
  name                    = "${local.prefix}-csv-processor"
  container_spec_gcs_path = var.dataflow_flex_template_path

  parameters = {
    INPUT_FILE          = "gs://${google_storage_bucket.input.name}/*.csv"
    OUTPUT_TABLE        = "${var.gcp_project_id}:${google_bigquery_dataset.raw.dataset_id}.generic_raw"
    ERROR_PATH          = "gs://${google_storage_bucket.error.name}/generic-errors/"
    WORKER_MACHINE_TYPE = var.dataflow_worker_machine_type
    NUM_WORKERS         = var.dataflow_num_workers
    MAX_WORKERS         = var.dataflow_max_workers
  }

  region = var.gcp_region

  skip_wait_on_job_termination = false

  depends_on = [
    google_storage_bucket.input,
    google_bigquery_dataset.raw
  ]
}

# ============================================================================
# DATAFLOW MONITORING
# ============================================================================

# Alert for Dataflow job failures
resource "google_monitoring_alert_policy" "dataflow_job_failure" {
  display_name = "${local.prefix} Dataflow Job Failure"
  combiner     = "OR"

  conditions {
    display_name = "Dataflow Job Failed"

    condition_threshold {
      filter          = "resource.type=\"dataflow_job\" AND metric.type=\"dataflow.googleapis.com/job/job_status\" AND metric.labels.status=\"FAILED\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = var.notification_channels
}

# Alert for Dataflow high element drop rate
resource "google_monitoring_alert_policy" "dataflow_drop_rate" {
  display_name = "${local.prefix} Dataflow High Element Drop Rate"
  combiner     = "OR"

  conditions {
    display_name = "Element Drop Rate > 1%"

    condition_threshold {
      filter          = "resource.type=\"dataflow_job\" AND metric.type=\"dataflow.googleapis.com/job/element_drop_rate\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01 # 1%

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channels
}

# ============================================================================
# DATAFLOW NETWORK CONFIGURATION
# ============================================================================

# Firewall rules for Dataflow
resource "google_compute_firewall" "dataflow_ingress" {
  name    = "${local.prefix}-dataflow-ingress"
  network = google_compute_network.main.name

  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["12345", "12346"] # Dataflow worker ports
  }

  allow {
    protocol = "udp"
    ports    = ["12345", "12346"]
  }

  source_ranges = ["10.0.0.0/8"] # From VPC

  target_tags = ["dataflow-worker"]
}

resource "google_compute_firewall" "dataflow_egress" {
  name    = "${local.prefix}-dataflow-egress"
  network = google_compute_network.main.name

  direction = "EGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["443"] # HTTPS for GCP APIs
  }

  destination_ranges = ["0.0.0.0/0"]

  target_tags = ["dataflow-worker"]
}


