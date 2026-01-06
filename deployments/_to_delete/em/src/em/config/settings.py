"""
EM Settings.

System identification and infrastructure configuration.
"""

# System identification
SYSTEM_ID = "EM"

# Entity dependencies (for EntityDependencyChecker)
# EM requires all 3 entities before FDP transformation
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

# GCS paths (templates - substitute {project} and {env} at runtime)
LANDING_BUCKET_TEMPLATE = "gs://{project}-landing-{env}/em"
ARCHIVE_BUCKET_TEMPLATE = "gs://{project}-archive-{env}/em"
ERROR_BUCKET_TEMPLATE = "gs://{project}-error-{env}/em"

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

# FDP Tables (JOIN: 3 sources → 1 target)
FDP_EM_ATTRIBUTES_TABLE = "em_attributes"

# Job control
JOB_CONTROL_DATASET = "job_control"
JOB_CONTROL_TABLE = "pipeline_jobs"

# File patterns
CUSTOMERS_FILE_PATTERN = "em_customers_{date}.csv"
ACCOUNTS_FILE_PATTERN = "em_accounts_{date}.csv"
DECISION_FILE_PATTERN = "em_decision_{date}.csv"
OK_FILE_SUFFIX = ".ok"

