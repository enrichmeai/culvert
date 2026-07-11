variable "gcp_project_id" {
  type        = string
  description = "GCP project the transform runs in."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the runner SA and Cloud Run job."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment."
}
variable "target_dataset" {
  type        = string
  description = "Dataset the transformed segments land into (shared substrate)."
}
variable "landing_bucket" {
  type        = string
  description = "Landing bucket holding the mainframe segment files (shared substrate)."
}
variable "staging_bucket" {
  type        = string
  description = "Staging bucket for the pipeline (shared substrate)."
}
variable "enable_cloud_run_job" {
  type        = string
  default     = "true"
  description = "Tier-3a demo executor on Cloud Run. String for CI."
}
variable "image_uri" {
  type        = string
  default     = ""
  description = "Container image for the Cloud Run executor job."
}
