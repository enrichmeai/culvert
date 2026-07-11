variable "gcp_project_id" {
  type        = string
  description = "GCP project the CDC stream runs in."
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
variable "odp_dataset_id" {
  type        = string
  description = "ODP dataset the CDC events land into (shared substrate)."
}
variable "cdc_subscription" {
  type        = string
  description = "Fully-qualified Pub/Sub subscription of inbound Debezium CDC events (shared substrate)."
}
variable "enable_cloud_run_job" {
  type        = string
  default     = "true"
  description = "Tier-3a demo executor on Cloud Run (scale-to-zero). String for CI."
}
variable "image_uri" {
  type        = string
  default     = ""
  description = "Container image for the Cloud Run executor job."
}
