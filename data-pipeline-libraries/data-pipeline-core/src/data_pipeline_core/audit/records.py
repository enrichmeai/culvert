"""The AuditRecord dataclass - the RETIRED pre-0.2.0 unit of audit emission.

Superseded by ``AuditEvent`` (``data_pipeline_core.audit.events``), which is
what the ``AuditEventPublisher`` contract now carries. ``AuditRecord`` modelled
a *stage summary* - eleven fields of durations, success flags and hashes -
while docs/CONTRACT.md section 4 specifies an *event*. The two share exactly
one column, ``run_id``, so there is no adapter between them.

Kept importable so existing references still resolve; do not use it in a
publisher path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class AuditRecord:
    """A stage summary emitted at a pipeline boundary (e.g. an ingestion stage
    completing). Retired - use ``AuditEvent`` instead.

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
