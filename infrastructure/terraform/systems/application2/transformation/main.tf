resource "google_bigquery_dataset" "odp_application2" {
  dataset_id    = "odp_application2"
  friendly_name = "Application2 Original Data Product"
  description   = "Raw 1:1 copy of Application2 mainframe data - Applications entity"
  location      = var.gcp_region


  # Default table expiration: none (keep indefinitely)
  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# FDP Dataset - Foundation Data Product (transformed)
resource "google_bigquery_dataset" "fdp_application2" {
  dataset_id    = "fdp_application2"
  friendly_name = "Application2 Foundation Data Product"
  description   = "Transformed Application2 data - portfolio_account_facility table"
  location      = var.gcp_region


  delete_contents_on_destroy = var.force_destroy

  labels = local.common_labels
}

# ============================================================================
# BIGQUERY - ODP TABLES
# ============================================================================

# ODP Applications table
resource "google_bigquery_table" "odp_applications" {
  dataset_id          = google_bigquery_dataset.odp_application2.dataset_id
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
# BIGQUERY - FDP TABLES (MAP transformation: 1 source → 1 target)
# ============================================================================

# FDP Portfolio Account Facility table
resource "google_bigquery_table" "fdp_portfolio_account_facility" {
  dataset_id          = google_bigquery_dataset.fdp_application2.dataset_id
  table_id            = "portfolio_account_facility"
  deletion_protection = !var.force_destroy

  time_partitioning {
    type  = "DAY"
    field = "application_date"
  }

  clustering = ["application_id", "customer_id"]

  schema = jsonencode([
    { name = "facility_key", type = "STRING", mode = "REQUIRED", description = "Unique facility identifier" },
    { name = "application_id", type = "STRING", mode = "REQUIRED", description = "Unique application identifier" },
    { name = "customer_id", type = "STRING", mode = "REQUIRED", description = "Customer identifier" },
    { name = "loan_amount", type = "NUMERIC", mode = "REQUIRED", description = "Requested loan amount" },
    { name = "interest_rate", type = "NUMERIC", mode = "NULLABLE", description = "Interest rate" },
    { name = "term_months", type = "INTEGER", mode = "NULLABLE", description = "Loan term in months" },
    { name = "application_date", type = "DATE", mode = "REQUIRED", description = "Application submission date" },
    { name = "application_status", type = "STRING", mode = "REQUIRED", description = "Current application status" },
    { name = "branch_code", type = "STRING", mode = "NULLABLE", description = "Branch code" },
    { name = "product_type", type = "STRING", mode = "NULLABLE", description = "Loan product type" },
    # Audit columns
    { name = "_run_id", type = "STRING", mode = "REQUIRED", description = "Pipeline run identifier" },
    { name = "_extract_date", type = "DATE", mode = "REQUIRED", description = "Extract date" },
    { name = "_transformed_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Transformation timestamp" },
  ])

  labels = local.common_labels
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

# Application2 Pipeline service account
