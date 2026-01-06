"""
LOA Ingestion Unit - ODP Producer

Reads mainframe extracts from GCS and loads to BigQuery ODP tables.
Pattern: SPLIT - Single entity (Applications) → Single ODP table

Pipeline Flow:
    1. Read CSV from GCS landing zone
    2. Parse HDR/TRL records
    3. Validate using schema-driven validation
    4. Write to odp_loa.applications
    5. Archive source files
"""

__version__ = "1.0.0"

from .config import SYSTEM_ID
from .pipeline import LOA_ENTITY_CONFIG, run_loa_pipeline

__all__ = [
    '__version__',
    'SYSTEM_ID',
    'LOA_ENTITY_CONFIG',
    'run_loa_pipeline',
]

