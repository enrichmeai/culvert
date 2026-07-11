# Per-deployment Terraform root for fdp-trigger.
# fdp-trigger is Cloud-Run-native: it owns its Cloud Run service, its runner
# service account, and the invoker IAM for Cloud Scheduler. Mirrors the shape in
# infrastructure/terraform/systems/generic (google_cloud_run_v2_service.
# fdp_trigger), self-contained here so the deployment stands alone.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
  backend "gcs" {
    prefix = "deployments/fdp-trigger"
  }
}
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
