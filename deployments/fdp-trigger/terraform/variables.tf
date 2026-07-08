variable "gcp_project_id" {
  type        = string
  description = "GCP project the trigger runs in."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the Cloud Run service and service account."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment (demo, dev, int, prod)."
}
variable "image_uri" {
  type        = string
  default     = ""
  description = "Container image for the fdp-trigger Cloud Run service."
}
variable "fdp_dataset" {
  type        = string
  default     = "fdp_generic"
  description = "FDP dataset the trigger watches for stability (injected substrate)."
}
variable "fdp_tables" {
  type        = list(string)
  default     = []
  description = "FDP tables the trigger watches."
}
variable "scheduler_service_account" {
  type        = string
  default     = ""
  description = "SA Cloud Scheduler uses to invoke (OIDC). Empty = no invoker binding."
}
