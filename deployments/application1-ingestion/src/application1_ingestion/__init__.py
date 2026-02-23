"""
Application1 Ingestion Unit - ODP Producer

Reads mainframe extracts from GCS and loads to BigQuery ODP tables.
Pattern: JOIN - 3 entities (Customers, Accounts, Decision) → 3 ODP tables

Pipeline Flow:
    1. Read CSV from GCS landing zone
    2. Parse HDR/TRL records
    3. Validate using schema-driven validation
    4. Write to odp_em.customers, odp_em.accounts, odp_em.decision
    5. Archive source files
    6. Wait for all 3 entities before triggering FDP transformation
"""

__version__ = "1.0.0"

from .config import SYSTEM_ID

__all__ = [
    '__version__',
    'SYSTEM_ID',
]

