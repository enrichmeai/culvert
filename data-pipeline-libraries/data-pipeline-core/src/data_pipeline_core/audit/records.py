"""The AuditRecord dataclass — the unit of audit emission.

Eleven fields, published at pipeline boundaries by an
`AuditEventPublisher` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class AuditRecord:
    """A single audit event emitted at a pipeline boundary (e.g. an
    ingestion stage completing).

    `audit_hash` is a deterministic content hash that downstream
    reconciliation uses to dedupe replays. `metadata` is the catch-all
    for stage-specific context (table identifiers, partition keys, etc.)
    """

    run_id: str
    pipeline_name: str
    entity_type: str
    source_file: str
    record_count: int
    processed_timestamp: datetime
    processing_duration_seconds: float
    success: bool
    error_count: int = 0
    audit_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
