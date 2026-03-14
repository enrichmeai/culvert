"""
Generic Ingestion Unit - ODP Producer

Reads mainframe extracts from GCS and loads to BigQuery ODP tables.
Pattern: JOIN - 4 entities (Customers, Accounts, Decision, Applications) → 4 ODP tables

Pipeline Flow:
    1. Read CSV from GCS landing zone
    2. Parse HDR/TRL records
    3. Validate using schema-driven validation
    4. Write to odp_generic.customers, odp_generic.accounts, odp_generic.decision, odp_generic.applications
    5. Archive source files
    6. Wait for all 4 entities before triggering FDP transformation

Installation:
    pip install gcp-pipeline-ref-ingestion

Extract reference code:
    gcp-ref-ingestion extract ./my-project
"""

__version__ = "1.0.7"

from .config import SYSTEM_ID

__all__ = [
    '__version__',
    'SYSTEM_ID',
]

