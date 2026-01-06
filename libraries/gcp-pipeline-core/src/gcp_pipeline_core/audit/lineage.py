"""
GDW Data Core - Data Lineage Module

Provides data lineage tracking for complete traceability from source
to cloud destination, supporting full audit and compliance requirements.
"""

from typing import Dict, Any
from .records import AuditRecord


class DataLineageTracker:
    """
    Track data lineage through the migration pipeline.

    Provides complete traceability from source to cloud destination
    for compliance and audit purposes.
    """

    @staticmethod
    def generate_data_lineage(audit_record: AuditRecord) -> Dict[str, Any]:
        """
        Generate data lineage information for audit record.

        Provides complete traceability from source to cloud destination.

        Args:
            audit_record: The audit record to generate lineage for

        Returns:
            Dictionary containing complete lineage information
        """
        lineage = {
            'source': {
                'system': 'Legacy System',
                'pipeline_name': audit_record.pipeline_name,
                'file': audit_record.source_file,
                'timestamp': audit_record.processed_timestamp.isoformat()
            },
            'pipeline': {
                'run_id': audit_record.run_id,
                'entity_type': audit_record.entity_type,
                'duration_seconds': audit_record.processing_duration_seconds,
                'status': 'SUCCESS' if audit_record.success else 'FAILED'
            },
            'destination': {
                'system': 'Cloud Warehouse',
                'table_raw': f"{audit_record.entity_type}_raw",
                'table_errors': f"{audit_record.entity_type}_errors",
                'record_count': audit_record.record_count,
                'error_count': audit_record.error_count
            },
            'audit': {
                'hash': audit_record.audit_hash,
                'metadata': audit_record.metadata
            }
        }

        return lineage


def generate_data_lineage(audit_record: AuditRecord) -> Dict[str, Any]:
    """
    Generate data lineage information for audit record.

    Provides complete traceability from source to cloud destination.

    This is a convenience function that wraps DataLineageTracker.generate_data_lineage()
    for backward compatibility.

    Args:
        audit_record: The audit record to generate lineage for

    Returns:
        Dictionary containing complete lineage information
    """
    return DataLineageTracker.generate_data_lineage(audit_record)

