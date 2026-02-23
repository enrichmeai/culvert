"""
Application1 Configuration Module.

System-specific configuration for the Application1 (Application A) pipeline.
"""

from .settings import (
    SYSTEM_ID,
    REQUIRED_ENTITIES,
    ODP_DATASET,
    FDP_DATASET,
    LANDING_BUCKET_TEMPLATE,
    ARCHIVE_BUCKET_TEMPLATE,
    ERROR_BUCKET_TEMPLATE,
)
from .constants import (
    CUSTOMERS_HEADERS,
    ACCOUNTS_HEADERS,
    DECISION_HEADERS,
    ALLOWED_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_DECISION_CODES,
    SCORE_MIN,
    SCORE_MAX,
)

__all__ = [
    # Settings
    'SYSTEM_ID',
    'REQUIRED_ENTITIES',
    'ODP_DATASET',
    'FDP_DATASET',
    'LANDING_BUCKET_TEMPLATE',
    'ARCHIVE_BUCKET_TEMPLATE',
    'ERROR_BUCKET_TEMPLATE',
    # Constants
    'CUSTOMERS_HEADERS',
    'ACCOUNTS_HEADERS',
    'DECISION_HEADERS',
    'ALLOWED_STATUSES',
    'ALLOWED_ACCOUNT_TYPES',
    'ALLOWED_DECISION_CODES',
    'SCORE_MIN',
    'SCORE_MAX',
]

