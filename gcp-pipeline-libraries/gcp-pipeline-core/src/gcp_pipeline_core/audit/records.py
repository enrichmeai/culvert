"""
GCP Pipeline Framework - Audit Records Module

Provides standard audit record and entry data structures for tracking
data migration operations and pipeline executions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class AuditRecord:
    """Standard audit record structure"""
    run_id: str
    pipeline_name: str
    entity_type: str  # e.g., applications, customers, branches, collateral
    source_file: str
    record_count: int
    processed_timestamp: datetime
    processing_duration_seconds: float
    success: bool
    error_count: int
    audit_hash: str
    metadata: Dict[str, Any]


@dataclass
class AuditEntry:
    """Individual entry in the audit trail"""
    timestamp: datetime
    run_id: str
    entity_type: str
    status: str  # SUCCESS, FAILURE, WARNING
    message: str
    context: Dict[str, Any]

