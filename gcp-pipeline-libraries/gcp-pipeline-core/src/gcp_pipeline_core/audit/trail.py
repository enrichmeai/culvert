"""
GDW Data Core - Audit Trail Module

Provides audit trail management for data migration pipelines.
Tracks pipeline executions and enables data lineage tracking.
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any
from .records import AuditRecord, AuditEntry
from .publisher import AuditPublisher

logger = logging.getLogger(__name__)


class AuditTrail:
    """
    Audit trail manager for data migration pipelines.

    Tracks all pipeline executions, provides data lineage,
    and enables reconciliation between source and cloud.
    """

    def __init__(self, run_id: str, pipeline_name: str, entity_type: str, publisher: AuditPublisher = None):
        self.run_id = run_id
        self.pipeline_name = pipeline_name
        self.entity_type = entity_type
        self.start_time = datetime.utcnow()
        self.records_processed = 0
        self.records_valid = 0
        self.records_error = 0
        self.metadata = {}
        self.entries: List[AuditEntry] = []
        self.publisher = publisher

    def log_entry(self, status: str, message: str, context: Dict[str, Any] = None):
        """Log a specific audit entry"""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            run_id=self.run_id,
            entity_type=self.entity_type,
            status=status,
            message=message,
            context=context or {}
        )
        self.entries.append(entry)
        logger.info("[AUDIT] %s: %s", status, message)

    def get_entries_by_status(self, status: str) -> List[AuditEntry]:
        """Get entries with a specific status"""
        return [e for e in self.entries if e.status == status]

    def get_entries_by_entity_type(self, entity_type: str) -> List[AuditEntry]:
        """Get entries with a specific entity type"""
        return [e for e in self.entries if e.entity_type == entity_type]

    def get_entry_count(self) -> int:
        """Get total number of entries"""
        return len(self.entries)

    def get_entry_count_by_status(self, status: str) -> int:
        """Get number of entries with a specific status"""
        return len(self.get_entries_by_status(status))

    def get_entries(self) -> List[AuditEntry]:
        """Get all entries in the audit trail"""
        return self.entries

    def record_processing_start(self, source_file: str, metadata: Dict[str, Any] = None):
        """Record start of processing"""
        self.source_file = source_file
        if metadata:
            self.metadata.update(metadata)

        # Log start
        logger.info("[AUDIT] Starting %s for %s", self.pipeline_name, self.entity_type)
        logger.info("[AUDIT] Run ID: %s", self.run_id)
        logger.info("[AUDIT] Source: %s", source_file)

    def record_processing_end(self, success: bool = True):
        """Record end of processing"""
        self.end_time = datetime.utcnow()
        duration = (self.end_time - self.start_time).total_seconds()

        # Create audit record
        audit_record = AuditRecord(
            run_id=self.run_id,
            pipeline_name=self.pipeline_name,
            entity_type=self.entity_type,
            source_file=self.source_file,
            record_count=self.records_processed,
            processed_timestamp=self.end_time,
            processing_duration_seconds=duration,
            success=success,
            error_count=self.records_error,
            audit_hash=self._generate_audit_hash(),
            metadata=self.metadata
        )

        # Log completion
        logger.info("[AUDIT] Completed %s", self.pipeline_name)
        logger.info(
            "[AUDIT] Records processed: %d (valid=%d, errors=%d, duration=%.2fs)",
            self.records_processed, self.records_valid, self.records_error, duration,
        )

        # Publish record if publisher is configured
        if self.publisher:
            try:
                msg_id = self.publisher.publish(audit_record)
                logger.info("[AUDIT] Published audit record: %s", msg_id)
            except Exception as e:
                logger.error("[AUDIT] Failed to publish audit record: %s", e)

        return audit_record

    def increment_counts(self, valid: int = 0, errors: int = 0):
        """Increment processing counts"""
        self.records_valid += valid
        self.records_error += errors
        self.records_processed = self.records_valid + self.records_error

    def _generate_audit_hash(self) -> str:
        """Generate hash for audit verification"""
        audit_data = f"{self.run_id}|{self.source_file}|{self.records_processed}|{self.end_time.isoformat()}"
        return hashlib.sha256(audit_data.encode()).hexdigest()


class DuplicateDetector:
    """
    Detect duplicate records across pipeline runs.

    Prevents processing the same data multiple times.
    """

    def __init__(self):
        self.seen_records = set()

    def is_duplicate(self, record: Any, existing_record: Any = None, key_fields: List[str] = None) -> bool:
        """
        Check if record is a duplicate of an existing record or has been seen before.

        Args:
            record: Current record (dict or id)
            existing_record: Record to compare against
            key_fields: Fields to use for comparison

        Returns:
            True if duplicate, False otherwise
        """
        if existing_record and key_fields:
            # Compare two records
            for field in key_fields:
                if record.get(field) != existing_record.get(field):
                    return False
            return True

        # Check against seen records
        record_id = record if isinstance(record, str) else str(record)
        if key_fields and isinstance(record, dict):
            record_id = "|".join([str(record.get(f)) for f in key_fields])

        if record_id in self.seen_records:
            return True

        self.seen_records.add(record_id)
        return False

    def find_duplicates(self, records: List[Dict[str, Any]], key_fields: List[str]) -> List[Dict[str, Any]]:
        """Find duplicates in a batch of records"""
        seen = {}
        duplicates = []

        for record in records:
            key = "|".join([str(record.get(f)) for f in key_fields])
            if key in seen:
                duplicates.append(record)
            else:
                seen[key] = record

        return duplicates

    def mark_as_processed(self, record_id: str):
        """Mark a record as processed"""
        self.seen_records.add(record_id)

    def get_duplicate_count(self) -> int:
        """Get count of unique records processed"""
        return len(self.seen_records)

