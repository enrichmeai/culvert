"""Audit records — the cloud-neutral data shape an AuditEventPublisher emits.

``AuditEvent`` (docs/CONTRACT.md section 4) is the contract shape and the one to
use. ``AuditRecord`` is the pre-0.2.0 stage-summary type it replaces; it is kept
importable only until the emitters move over (migration-plan Phase 1). The two
share exactly one column, ``run_id`` — see MIGRATION.md.
"""

from data_pipeline_core.audit.events import CONTRACT_VERSION, AuditEvent, EventKind
from data_pipeline_core.audit.records import AuditRecord

__all__ = ["AuditEvent", "EventKind", "CONTRACT_VERSION", "AuditRecord"]
