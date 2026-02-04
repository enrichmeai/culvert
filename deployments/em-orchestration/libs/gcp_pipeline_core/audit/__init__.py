"""
GDW Data Core - Audit Framework

Centralized audit trail, reconciliation, and data lineage tracking.
Provides data lineage, duplicate detection, and reconciliation capabilities.

Used by: ALL migration pipelines
"""

from .records import AuditRecord, AuditEntry
from .reconciliation import (
    ReconciliationReport,
    ReconciliationEngine,
    ReconciliationResult,
    ReconciliationStatus,
)
from .trail import AuditTrail, DuplicateDetector
from .lineage import DataLineageTracker, generate_data_lineage
from .publisher import AuditPublisher

__all__ = [
    # Records
    'AuditRecord',
    'AuditEntry',
    # Reconciliation
    'ReconciliationReport',
    'ReconciliationEngine',
    'ReconciliationResult',
    'ReconciliationStatus',
    # Trail
    'AuditTrail',
    'DuplicateDetector',
    # Lineage
    'DataLineageTracker',
    'generate_data_lineage',
    # Publisher
    'AuditPublisher',
]

