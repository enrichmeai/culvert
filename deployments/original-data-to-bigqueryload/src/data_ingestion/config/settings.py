"""
Generic Settings.

System identification and infrastructure configuration.
Tries loading from YAML config first; falls back to hardcoded values.
"""

import logging

logger = logging.getLogger(__name__)

# --- Attempt YAML-driven settings ---
_yaml_settings = None
try:
    from .config_loader import load_system_config, build_settings
    _config = load_system_config()
    _yaml_settings = build_settings(_config)
    logger.debug("Loaded settings from system.yaml")
except FileNotFoundError:
    logger.debug("system.yaml not found, using hardcoded settings")
except Exception as e:
    logger.warning(f"Failed to load YAML settings: {e}, using hardcoded settings")


if _yaml_settings is not None:
    # YAML-driven values
    SYSTEM_ID = _yaml_settings["system_name"]
    REQUIRED_ENTITIES = _yaml_settings["required_entities"]
    ODP_DATASET = _yaml_settings["odp_dataset"]
    FDP_DATASET = _yaml_settings["fdp_dataset"]
    JOB_CONTROL_DATASET = _yaml_settings["job_control_dataset"]
    LANDING_BUCKET_TEMPLATE = "gs://" + _yaml_settings["landing_bucket_template"]
    ARCHIVE_BUCKET_TEMPLATE = "gs://" + _yaml_settings["archive_bucket_template"]
    ERROR_BUCKET_TEMPLATE = "gs://" + _yaml_settings["error_bucket_template"]
else:
    # Hardcoded fallback values
    SYSTEM_ID = "Generic"
    REQUIRED_ENTITIES = ["customers", "accounts", "decision", "applications"]
    LANDING_BUCKET_TEMPLATE = "gs://{project}-landing-{env}/generic"
    ARCHIVE_BUCKET_TEMPLATE = "gs://{project}-archive-{env}/generic"
    ERROR_BUCKET_TEMPLATE = "gs://{project}-error-{env}/generic"
    ODP_DATASET = "odp_generic"
    FDP_DATASET = "fdp_generic"
    JOB_CONTROL_DATASET = "job_control"

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
JOB_CONTROL_TABLE = "pipeline_jobs"

# File patterns
CUSTOMERS_FILE_PATTERN = "generic_customers_{date}.csv"
ACCOUNTS_FILE_PATTERN = "generic_accounts_{date}.csv"
DECISION_FILE_PATTERN = "generic_decision_{date}.csv"
APPLICATIONS_FILE_PATTERN = "generic_applications_{date}.csv"
OK_FILE_SUFFIX = ".ok"
