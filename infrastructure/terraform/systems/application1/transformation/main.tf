locals {
  common_labels = {
    project     = "gcp-pipeline-builder"
    system      = "application1"
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_bigquery_dataset" "odp_application1" {
  dataset_id    = "odp_application1"
  friendly_name = "ODP Application1 - Original Data Product"
  description   = "Raw data from Application1 mainframe extracts (customers, accounts, decision)"
  location      = var.bq_location

  labels = local.common_labels
}

# FDP dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_application1" {
  dataset_id    = "fdp_application1"
  friendly_name = "FDP Application1 - Foundation Data Product"
  description   = "Transformed Application1 data (event_transaction_excess and portfolio_account_excess)"
  location      = var.bq_location

  labels = local.common_labels
}

# Job control dataset (shared across systems)
resource "google_bigquery_dataset" "job_control" {
  dataset_id    = "job_control"
  friendly_name = "Pipeline Job Control"
  description   = "Job tracking and status for all pipelines"
  location      = var.bq_location

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY TABLES - ODP (Customers, Accounts, Decision)
# ============================================================================

# ODP: Customers table
resource "google_bigquery_table" "odp_customers" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "customers"

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "_run_id"]

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "first_name", type = "STRING", mode = "NULLABLE", description = "First name" },
    { name = "last_name", type = "STRING", mode = "NULLABLE", description = "Last name" },
    { name = "ssn", type = "STRING", mode = "NULLABLE", description = "Social Security Number (PII)" },
    { name = "dob", type = "DATE", mode = "NULLABLE", description = "Date of birth (PII)" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "A=Active, I=Inactive, C=Closed" },
    { name = "created_date", type = "DATE", mode = "NULLABLE", description = "Customer creation date" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels
}

# ODP: Customers errors table
resource "google_bigquery_table" "odp_customers_errors" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "customers_errors"

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels
}

# ODP: Accounts table
resource "google_bigquery_table" "odp_accounts" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "accounts"

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["account_id", "customer_id", "_run_id"]

  schema = jsonencode([
    { name = "account_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Foreign key to customers" },
    { name = "account_type", type = "STRING", mode = "NULLABLE", description = "CHECKING, SAVINGS, MONEY_MARKET, CD, IRA" },
    { name = "balance", type = "NUMERIC", mode = "NULLABLE", description = "Current balance" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "A=Active, I=Inactive, C=Closed" },
    { name = "open_date", type = "DATE", mode = "NULLABLE", description = "Account open date" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels
}

# ODP: Accounts errors table
resource "google_bigquery_table" "odp_accounts_errors" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "accounts_errors"

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels
}

# ODP: Decision table
resource "google_bigquery_table" "odp_decision" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "decision"

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["decision_id", "customer_id", "_run_id"]

  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "REQUIRED", description = "Primary key" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Foreign key to customers" },
    { name = "application_id", type = "STRING", mode = "NULLABLE", description = "Related application" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED", description = "APPROVE, DECLINE, REVIEW, PENDING" },
    { name = "decision_date", type = "TIMESTAMP", mode = "REQUIRED", description = "When decision was made" },
    { name = "score", type = "INTEGER", mode = "NULLABLE", description = "Credit score (300-850)" },
    { name = "reason_codes", type = "STRING", mode = "NULLABLE", description = "Pipe-separated reason codes" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE", description = "Source file path" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR" }
  ])

  labels = local.common_labels
}

# ODP: Decision errors table
resource "google_bigquery_table" "odp_decision_errors" {
  dataset_id = google_bigquery_dataset.odp_application1.dataset_id
  table_id   = "decision_errors"

  time_partitioning {
    type  = "DAY"
    field = "_processed_at"
  }

  schema = jsonencode([
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_field", type = "STRING", mode = "NULLABLE" },
    { name = "raw_record", type = "JSON", mode = "NULLABLE" }
  ])

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY TABLES - FDP
# ============================================================================

# FDP Event Transaction Excess table
resource "google_bigquery_table" "fdp_event_transaction_excess" {
  dataset_id          = google_bigquery_dataset.fdp_application1.dataset_id
  table_id            = "event_transaction_excess"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "account_id"]

  schema = jsonencode([
    { name = "event_key", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "ssn_masked", type = "STRING", mode = "NULLABLE" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "date_of_birth", type = "DATE", mode = "NULLABLE" },
    { name = "customer_status", type = "STRING", mode = "NULLABLE" },
    { name = "account_id", type = "STRING", mode = "REQUIRED" },
    { name = "account_type_desc", type = "STRING", mode = "NULLABLE" },
    { name = "current_balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "account_open_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = local.common_labels
}

# FDP Portfolio Account Excess table
resource "google_bigquery_table" "fdp_portfolio_account_excess" {
  dataset_id          = google_bigquery_dataset.fdp_application1.dataset_id
  table_id            = "portfolio_account_excess"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["customer_id", "decision_id"]

  schema = jsonencode([
    { name = "portfolio_key", type = "STRING", mode = "REQUIRED" },
    { name = "decision_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "decision_code", type = "STRING", mode = "REQUIRED" },
    { name = "decision_outcome", type = "STRING", mode = "NULLABLE" },
    { name = "decision_date", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "score", type = "INTEGER", mode = "NULLABLE" },
    { name = "decision_reason", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "REQUIRED" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = local.common_labels
}

