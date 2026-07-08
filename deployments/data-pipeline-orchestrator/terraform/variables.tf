variable "gcp_project_id" {
  type        = string
  description = "GCP project the orchestrator runs in."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the runner SA and (optional) Composer environment."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment (demo, dev, int, prod)."
}
variable "enable_composer" {
  type        = string
  default     = "false"
  description = <<-EOT
    Tier-3b switch. false (default, Tier-3a demo): NO Composer environment is
    created — zero standing cost; orchestrate via Cloud Scheduler -> Cloud Run
    or local Airflow. true: provision a small Composer environment for the
    one-off pre-publish validation, then tear it down. String, not bool, so
    `-var enable_composer=true` reads cleanly from CI.
  EOT
}
