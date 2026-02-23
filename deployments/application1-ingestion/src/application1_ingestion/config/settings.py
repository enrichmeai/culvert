"""
Application1 Settings.

System identification and infrastructure configuration.
"""

# System identification
SYSTEM_ID = "Application1"

# Entity dependencies (for EntityDependencyChecker)
# Application1 requires all 3 entities before FDP transformation
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

# GCS paths (templates - substitute {project} and {env} at runtime)
LANDING_BUCKET_TEMPLATE = "gs://{project}-landing-{env}/application1"
ARCHIVE_BUCKET_TEMPLATE = "gs://{project}-archive-{env}/application1"
ERROR_BUCKET_TEMPLATE = "gs://{project}-error-{env}/application1"

# BigQuery datasets
ODP_DATASET = "odp_em"
FDP_DATASET = "fdp_em"

# ODP Tables
ODP_CUSTOMERS_TABLE = "customers"
ODP_ACCOUNTS_TABLE = "accounts"
ODP_DECISION_TABLE = "decision"

# Error tables
ODP_CUSTOMERS_ERRORS_TABLE = "customers_errors"
ODP_ACCOUNTS_ERRORS_TABLE = "accounts_errors"
ODP_DECISION_ERRORS_TABLE = "decision_errors"

# FDP Tables (MULTI-TARGET)
FDP_EVENT_TRANSACTION_EXCESS_TABLE = "event_transaction_excess"
FDP_PORTFOLIO_ACCOUNT_EXCESS_TABLE = "portfolio_account_excess"

# Job control
JOB_CONTROL_DATASET = "job_control"
JOB_CONTROL_TABLE = "pipeline_jobs"

# File patterns
CUSTOMERS_FILE_PATTERN = "application1_customers_{date}.csv"
ACCOUNTS_FILE_PATTERN = "application1_accounts_{date}.csv"
DECISION_FILE_PATTERN = "application1_decision_{date}.csv"
OK_FILE_SUFFIX = ".ok"

