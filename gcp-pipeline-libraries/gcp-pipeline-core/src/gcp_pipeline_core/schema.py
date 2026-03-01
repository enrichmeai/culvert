"""
Entity Schema Types.

Base classes for defining entity schemas.
Pipelines import these and define their specific schemas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class SchemaField:
    """Definition of a schema field."""
    name: str
    field_type: str  # STRING, INTEGER, NUMERIC, DATE, TIMESTAMP, BOOLEAN
    required: bool = False
    description: str = ""
    max_length: Optional[int] = None
    allowed_values: Optional[List[str]] = None
    is_pii: bool = False
    pii_type: Optional[str] = None  # e.g., SSN, EMAIL, FULL, PARTIAL
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[str] = None  # e.g., "customers.customer_id"
    enrichment_rules: Optional[List[Dict[str, Any]]] = None  # Enrichment configuration


@dataclass
class EntitySchema:
    """Schema definition for an entity."""
    entity_name: str
    system_id: str
    fields: List[SchemaField]
    primary_key: List[str]
    description: str = ""
    partition_field: Optional[str] = None
    cluster_fields: Optional[List[str]] = None

    def get_field(self, name: str) -> Optional[SchemaField]:
        """Get field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [f.name for f in self.fields if f.required]

    def get_pii_fields(self) -> List[str]:
        """Get list of PII field names."""
        return [f.name for f in self.fields if f.is_pii]

    def get_primary_key_fields(self) -> List[str]:
        """Get list of primary key field names."""
        return [f.name for f in self.fields if f.is_primary_key]

    def to_bq_schema(self, include_audit: bool = True) -> List[Dict[str, Any]]:
        """
        Convert to BigQuery schema format.

        Args:
            include_audit: Whether to include audit columns

        Returns:
            List of BigQuery schema field definitions
        """
        type_mapping = {
            "STRING": "STRING",
            "INTEGER": "INT64",
            "NUMERIC": "NUMERIC",
            "DATE": "DATE",
            "TIMESTAMP": "TIMESTAMP",
            "BOOLEAN": "BOOL",
        }

        schema = []
        for f in self.fields:
            schema.append({
                "name": f.name,
                "type": type_mapping.get(f.field_type, "STRING"),
                "mode": "REQUIRED" if f.required else "NULLABLE",
                "description": f.description,
            })

        if include_audit:
            schema.extend([
                {"name": "_run_id", "type": "STRING", "mode": "REQUIRED",
                 "description": "Pipeline run ID"},
                {"name": "_source_file", "type": "STRING", "mode": "NULLABLE",
                 "description": "Source file path"},
                {"name": "_processed_at", "type": "TIMESTAMP", "mode": "REQUIRED",
                 "description": "Processing timestamp"},
            ])

        return schema

    def get_csv_headers(self) -> List[str]:
        """Get list of CSV column headers."""
        return [f.name for f in self.fields]


__all__ = [
    'SchemaField',
    'EntitySchema',
]

