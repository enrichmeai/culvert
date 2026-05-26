# Bootstrap Terraform Configuration
#
# This module creates the prerequisite infrastructure needed before
# the main Terraform configurations can run:
# - GCS bucket for Terraform state
# - Enable required GCP APIs
#
# Run this FIRST before running any other Terraform:
#   cd infrastructure/terraform/bootstrap
#   terraform init
#   terraform apply -var="gcp_project_id=YOUR_PROJECT_ID"

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Bootstrap uses local state - no remote backend yet!
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west2"
}

# ============================================================================
# ENABLE REQUIRED APIS
# ============================================================================

resource "google_project_service" "required_apis" {
  for_each = toset([
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "dataflow.googleapis.com",
    "pubsub.googleapis.com",
    "composer.googleapis.com",
    "containerregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project                    = var.gcp_project_id
  service                    = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
}

# ============================================================================
# TERRAFORM STATE BUCKET
# ============================================================================

resource "google_storage_bucket" "terraform_state" {
  name          = "gcp-pipeline-terraform-state"
  location      = var.gcp_region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 5
    }
  }

  labels = {
    purpose    = "terraform-state"
    managed_by = "terraform-bootstrap"
  }

  depends_on = [google_project_service.required_apis]
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "terraform_state_bucket" {
  description = "GCS bucket for Terraform state"
  value       = google_storage_bucket.terraform_state.name
}

output "enabled_apis" {
  description = "List of enabled GCP APIs"
  value       = [for api in google_project_service.required_apis : api.service]
}

output "next_steps" {
  description = "Next steps after bootstrap"
  value       = <<-EOT

    ✅ Bootstrap complete!

    Terraform state bucket created: ${google_storage_bucket.terraform_state.name}

    Next steps:
    1. Run the main infrastructure:
       cd ../systems/generic/ingestion
       terraform init
       terraform apply -var="gcp_project_id=${var.gcp_project_id}"

    2. Or trigger via GitHub Actions:
       gh workflow run deploy-generic.yml -f environment=dev -f library_version=1.0.7
  EOT
}

