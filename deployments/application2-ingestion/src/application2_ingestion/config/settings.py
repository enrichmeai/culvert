"""
Application2 Settings.

System identification and infrastructure configuration.
"""

# System identification
SYSTEM_ID = "Application2"

# Entity dependencies (single entity - no dependency wait needed)
# Application2 immediately triggers FDP after ODP load (unlike Application1 which waits for 3 entities)
REQUIRED_ENTITIES = ["applications"]

# GCS paths (templates - substitute {project} and {env} at runtime)
LANDING_BUCKET_TEMPLATE = "gs://{project}-landing-{env}/application2"
ARCHIVE_BUCKET_TEMPLATE = "gs://{project}-archive-{env}/application2"
ERROR_BUCKET_TEMPLATE = "gs://{project}-error-{env}/application2"

# BigQuery datasets
ODP_DATASET = "odp_loa"
FDP_DATASET = "fdp_loa"

# ODP Tables (single entity)
ODP_APPLICATIONS_TABLE = "applications"

# Error tables
ODP_APPLICATIONS_ERRORS_TABLE = "applications_errors"

# FDP Tables (MAP: 1 source → 1 target)
FDP_PORTFOLIO_ACCOUNT_FACILITY_TABLE = "portfolio_account_facility"
FDP_EVENT_TRANSACTION_EXCESS_TABLE = "event_transaction_excess"
FDP_PORTFOLIO_ACCOUNT_EXCESS_TABLE = "portfolio_account_excess"

# Job control
JOB_CONTROL_DATASET = "job_control"
JOB_CONTROL_TABLE = "pipeline_jobs"

# File patterns
APPLICATIONS_FILE_PATTERN = "application2_applications_{date}.csv"
OK_FILE_SUFFIX = ".ok"

