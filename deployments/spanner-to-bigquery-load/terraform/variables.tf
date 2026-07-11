variable "gcp_project_id" {
  type        = string
  description = "GCP project the dbt run targets."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the runner SA."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment."
}
variable "target_dataset" {
  type        = string
  default     = "fdp_spanner"
  description = "BigQuery dataset the models write (shared substrate)."
}
variable "spanner_connection_id" {
  type        = string
  description = "BigQuery external connection to Spanner, as location.connection_id (e.g. us.spanner-conn). The runner SA is granted connectionUser on it."
}
