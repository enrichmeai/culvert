resource "google_bigquery_dataset" "odp_loa" {
  dataset_id    = "odp_loa"
  friendly_name = "LOA Original Data Product"
  description   = "Raw 1:1 copy of LOA mainframe data - Applications entity"
  location      = var.gcp_region


  # Default table expiration: none (keep indefinitely)
  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# FDP Dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_loa" {
  dataset_id    = "fdp_loa"
  friendly_name = "LOA Foundation Data Product"
  description   = "Transformed LOA data - event_transaction_excess and portfolio_account_excess tables"
  location      = var.gcp_region


  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY - ODP TABLES
# ============================================================================

# ODP Applications table
resource "google_bigquery_table" "odp_applications" {
  dataset_id          = google_bigquery_dataset.odp_loa.dataset_id
  table_id            = "applications"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "_extract_date"
  }

  clustering = ["application_id"]

  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Unique application identifier" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Customer identifier" },
    { name = "ssn", type = "STRING", mode = "NULLABLE", description = "Social Security Number (masked)" },
    { name = "loan_amount", type = "NUMERIC", mode = "REQUIRED", description = "Requested loan amount" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE", description = "Interest rate" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE", description = "Loan term in months" },
    { name = "application_date", type = "DATE", mode = "REQUIRED", description = "Application submission date" },
    { name = "application_status", type = "STRING", mode = "REQUIRED", description = "Current application status" },
    { name = "branch_code", type = "STRING", mode = "NULLABLE", description = "Branch code" },
    { name = "product_type", type = "STRING", mode = "NULLABLE", description = "Loan product type" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_file", type = "STRING", mode = "REQUIRED", description = "Source file name" },
    { name = "_processed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Processing timestamp" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date from HDR record" },
  ])

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY - FDP TABLES (Split transformation: 1 source → 2 targets)
# ============================================================================

# FDP Event Transaction Excess table
resource "google_bigquery_table" "fdp_event_transaction_excess" {
  dataset_id          = google_bigquery_dataset.fdp_loa.dataset_id
  table_id            = "event_transaction_excess"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "event_date"
  }

  clustering = ["application_id", "event_type"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED", description = "Unique event identifier" },
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Source application ID" },
    { name = "event_type", type = "STRING", mode = "REQUIRED", description = "Type of event" },
    { name = "event_date", type = "DATE", mode = "REQUIRED", description = "Event date" },
    { name = "transaction_amount", type = "NUMERIC", mode = "NULLABLE", description = "Transaction amount" },
    { name = "excess_amount", type = "NUMERIC", mode = "NULLABLE", description = "Excess amount" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_source_application_id", type = "STRING", mode = "REQUIRED", description = "Source application ID" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
  ])

  labels = local.common_labels
}

# FDP Portfolio Account Excess table
resource "google_bigquery_table" "fdp_portfolio_account_excess" {
  dataset_id          = google_bigquery_dataset.fdp_loa.dataset_id
  table_id            = "portfolio_account_excess"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "reporting_date"
  }

  clustering = ["portfolio_id", "account_type"]

  schema = jsonencode([
    { name = "portfolio_id", type = "STRING", mode = "REQUIRED", description = "Portfolio identifier" },
    { name = "account_type", type = "STRING", mode = "REQUIRED", description = "Account type" },
    { name = "reporting_date", type = "DATE", mode = "REQUIRED", description = "Reporting date" },
    { name = "total_excess", type = "NUMERIC", mode = "NULLABLE", description = "Total excess amount" },
    { name = "application_count", type = "INTEGER", mode = "NULLABLE", description = "Number of applications" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_transformed_ts", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
  ])

  labels = local.common_labels
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# LOA Pipeline service account
