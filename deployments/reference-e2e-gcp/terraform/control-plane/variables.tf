variable "project_id" {
  type        = string
  description = "GCP project the proof runs in."
}

variable "project_number" {
  type        = string
  description = "That project's number. Composer 2 needs it to grant its service agent the V2 extension role."
}

variable "region" {
  type        = string
  description = "Region for Cloud SQL, Composer and the Dataflow workers."
}

variable "name_prefix" {
  type        = string
  description = "Prefix for every resource name."
  nullable    = false
  default     = "ref-e2e"
}

# ---- Network ---------------------------------------------------------------------------------

variable "network" {
  type        = string
  description = "Name of the existing VPC network that Cloud SQL (private IP) and Composer share."
  nullable    = false
  default     = "default"
}

variable "subnetwork" {
  type        = string
  description = "Name of the existing subnetwork, in var.region, that the Composer nodes use."
  nullable    = false
  default     = "default"
}

variable "create_private_service_access" {
  type        = bool
  description = <<-EOT
    Reserve a range and peer the VPC with Google's service networking, which a private-IP Cloud SQL
    instance needs. Set false when the network already has private service access.
  EOT
  nullable    = false
  default     = true
}

variable "private_service_prefix_length" {
  type        = number
  description = "Size of the range reserved for private service access (a /20 holds several instances)."
  nullable    = false
  default     = 20
}

# ---- Cloud SQL -------------------------------------------------------------------------------

variable "sql_tier" {
  type        = string
  description = "Cloud SQL machine type. The default is 1 vCPU and 3.75 GB."
  nullable    = false
  default     = "db-custom-1-3840"
}

variable "sql_disk_gb" {
  type        = number
  description = "SSD size in GB. The control-plane tables are small; this is the floor, and it autoresizes."
  nullable    = false
  default     = 10
}

variable "claim_idle_timeout_ms" {
  type        = number
  description = <<-EOT
    idle_in_transaction_session_timeout, in milliseconds. A stage claim is a row lock held by an
    open transaction (PostgresStageClaim), so a claimant that hangs while still connected keeps its
    claim until the server ends its session. This timeout is that end. It must be longer than the
    longest stage: a stage holds its transaction open, idle, while it works, and a stage that
    outlives the timeout loses its claim and cannot complete. Scenario 3 of the proof (#232) runs
    with 5000.
  EOT
  nullable    = false
  default     = 600000
  validation {
    condition     = var.claim_idle_timeout_ms > 0
    error_message = "claim_idle_timeout_ms must be positive: 0 disables the timeout, and a hung claimant would then hold its claim forever."
  }
}

variable "tcp_keepalives_idle" {
  type        = number
  description = "Seconds of silence before the server probes a client. Ends sessions whose client vanished without closing."
  nullable    = false
  default     = 60
}

variable "tcp_keepalives_interval" {
  type        = number
  description = "Seconds between unanswered keepalive probes."
  nullable    = false
  default     = 10
}

variable "tcp_keepalives_count" {
  type        = number
  description = "Unanswered probes before the server drops the connection."
  nullable    = false
  default     = 6
}

variable "max_concurrent_stages" {
  type        = number
  description = <<-EOT
    How many stages may run at once across the fan-out: max_concurrency in the DAG (#199) times
    the number of DAGs that run together. It sizes the Composer workers and the database's
    max_connections, because each running stage holds one connection for its claim.
  EOT
  nullable    = false
  default     = 4
  validation {
    # Each slot is a Celery process on a 0.5 vCPU, 2 GB worker; the stages mostly wait on Dataflow,
    # but past 16 the worker size has to grow with it.
    condition     = var.max_concurrent_stages >= 1 && var.max_concurrent_stages <= 16
    error_message = "max_concurrent_stages must be between 1 and 16 with the default worker size."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Protect the Cloud SQL instance from terraform destroy. False by default so the proof tears down in one command."
  nullable    = false
  default     = false
}

variable "password_version" {
  type        = number
  description = "Bump to generate and set a new database password (it is written to Secret Manager and the user, never to state)."
  nullable    = false
  default     = 1
}

# ---- Composer --------------------------------------------------------------------------------

variable "composer_image_version" {
  type        = string
  description = "Composer 2 image. The default is the one infrastructure/terraform/systems/generic already pins."
  nullable    = false
  default     = "composer-2.16.1-airflow-2.10.5"
}

variable "composer_environment_size" {
  type        = string
  description = "ENVIRONMENT_SIZE_SMALL, _MEDIUM or _LARGE: it sizes Airflow's own database and sets the environment fee."
  nullable    = false
  default     = "ENVIRONMENT_SIZE_SMALL"
}

variable "composer_worker_max_count" {
  type        = number
  description = "Most Airflow workers Composer scales to."
  nullable    = false
  default     = 2
}

# ---- Dataflow --------------------------------------------------------------------------------

variable "staging_bucket" {
  type        = string
  description = "Existing bucket the Dataflow workers stage and write temp files to."
}
