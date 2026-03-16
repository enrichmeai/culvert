# =============================================================================
# GCP Services Configuration
# =============================================================================
# This file enables all required GCP APIs for the pipeline infrastructure.
# Run: terraform apply -target=google_project_service.required_services
# =============================================================================

# List of all required GCP services
variable "required_services" {
  description = "GCP APIs required for the data pipeline infrastructure"
  type        = list(string)
  default = [
    # ==========================================================================
    # Core Services (Always Required)
    # ==========================================================================
    "storage.googleapis.com",              # Cloud Storage
    "bigquery.googleapis.com",             # BigQuery
    "pubsub.googleapis.com",               # Pub/Sub
    "iam.googleapis.com",                  # IAM
    "cloudresourcemanager.googleapis.com", # Resource Manager
    "serviceusage.googleapis.com",         # Service Usage API

    # ==========================================================================
    # Compute Services
    # ==========================================================================
    "container.googleapis.com",            # GKE (for Airflow)
    "dataflow.googleapis.com",             # Dataflow (for Beam pipelines)
    "compute.googleapis.com",              # Compute Engine (for GKE nodes)

    # ==========================================================================
    # Build & Deploy Services
    # ==========================================================================
    "cloudbuild.googleapis.com",           # Cloud Build
    "containerregistry.googleapis.com",    # Container Registry (GCR)
    "artifactregistry.googleapis.com",     # Artifact Registry

    # ==========================================================================
    # Monitoring & Observability
    # ==========================================================================
    "monitoring.googleapis.com",           # Cloud Monitoring
    "logging.googleapis.com",              # Cloud Logging
    "cloudtrace.googleapis.com",           # Cloud Trace
    "clouderrorreporting.googleapis.com",  # Error Reporting

    # ==========================================================================
    # Security Services
    # ==========================================================================
    "secretmanager.googleapis.com",        # Secret Manager
    "cloudkms.googleapis.com",             # Cloud KMS (encryption)
    "iamcredentials.googleapis.com",       # IAM Credentials

    # ==========================================================================
    # Optional Services (uncomment if needed)
    # ==========================================================================
    # "composer.googleapis.com",           # Cloud Composer (alternative to GKE)
    # "run.googleapis.com",                # Cloud Run
    # "cloudfunctions.googleapis.com",     # Cloud Functions
    # "cloudscheduler.googleapis.com",     # Cloud Scheduler
    # "spanner.googleapis.com",            # Cloud Spanner
  ]
}

# Enable all required services
resource "google_project_service" "required_services" {
  for_each = toset(var.required_services)

  project = var.gcp_project_id
  service = each.value

  # Don't disable services when destroying (prevents breaking other resources)
  disable_dependent_services = false
  disable_on_destroy         = false

  timeouts {
    create = "10m"
    update = "10m"
  }
}

# =============================================================================
# Service Dependencies
# =============================================================================
# Some services require other services to be enabled first

# GKE requires Compute Engine
resource "google_project_service" "gke_dependencies" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
  ])

  project = var.gcp_project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# Dataflow requires Compute Engine
resource "google_project_service" "dataflow_dependencies" {
  for_each = toset([
    "compute.googleapis.com",
    "dataflow.googleapis.com",
  ])

  project = var.gcp_project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# =============================================================================
# Outputs
# =============================================================================

output "enabled_services" {
  description = "List of enabled GCP services"
  value       = [for s in google_project_service.required_services : s.service]
}

output "services_status" {
  description = "Status of each enabled service"
  value = {
    for s in google_project_service.required_services :
    s.service => "enabled"
  }
}

