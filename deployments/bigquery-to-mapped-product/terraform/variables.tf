variable "gcp_project_id" {
  type        = string
  description = "GCP project the dbt run targets."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the runner service account."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment (demo, dev, int, prod)."
}
variable "source_dataset" {
  type        = string
  default     = "odp_generic"
  description = "Existing source dataset the models read (shared substrate)."
}
variable "target_dataset" {
  type        = string
  default     = "fdp_generic"
  description = "Existing target dataset the models write (shared substrate)."
}
