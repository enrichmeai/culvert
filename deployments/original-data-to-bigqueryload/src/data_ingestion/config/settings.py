"""
Generic Settings.

System identification and infrastructure configuration.
"""

# System identification
SYSTEM_ID = "Generic"

# Entity dependencies (for EntityDependencyChecker)
# Generic requires all 4 entities before FDP transformation
REQUIRED_ENTITIES = ["customers", "accounts", "decision", "applications"]

# GCS paths (templates - substitute {project} and {env} at runtime)
LANDING_BUCKET_TEMPLATE = "gs://{project}-landing-{env}/generic"
ARCHIVE_BUCKET_TEMPLATE = "gs://{project}-archive-{env}/generic"
ERROR_BUCKET_TEMPLATE = "gs://{project}-error-{env}/generic"

# BigQuery datasets — must match Terraform: infrastructure/terraform/systems/generic/
ODP_DATASET = "odp_generic"
FDP_DATASET = "fdp_generic"

# ODP Tables
ODP_CUSTOMERS_TABLE = "customers"
ODP_ACCOUNTS_TABLE = "accounts"
ODP_DECISION_TABLE = "decision"
ODP_APPLICATIONS_TABLE = "applications"

# Error tables
ODP_CUSTOMERS_ERRORS_TABLE = "customers_errors"
ODP_ACCOUNTS_ERRORS_TABLE = "accounts_errors"
ODP_DECISION_ERRORS_TABLE = "decision_errors"
ODP_APPLICATIONS_ERRORS_TABLE = "applications_errors"

# FDP Tables (MULTI-TARGET)
FDP_EVENT_TRANSACTION_EXCESS_TABLE = "event_transaction_excess"
FDP_PORTFOLIO_ACCOUNT_EXCESS_TABLE = "portfolio_account_excess"
FDP_PORTFOLIO_ACCOUNT_FACILITY_TABLE = "portfolio_account_facility"

# Job control
JOB_CONTROL_DATASET = "job_control"
JOB_CONTROL_TABLE = "pipeline_jobs"

# File patterns
CUSTOMERS_FILE_PATTERN = "generic_customers_{date}.csv"
ACCOUNTS_FILE_PATTERN = "generic_accounts_{date}.csv"
DECISION_FILE_PATTERN = "generic_decision_{date}.csv"
APPLICATIONS_FILE_PATTERN = "generic_applications_{date}.csv"
OK_FILE_SUFFIX = ".ok"

