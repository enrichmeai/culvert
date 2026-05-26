"""DataClassification enum — the taxonomic levels for sensitive data.

The values follow the common four-tier model used by Dataplex, AWS
Macie, and Azure Purview. Stage 3's `@governed` decorator uses this
enum on field-level metadata so the runtime knows what masking policy
to apply.
"""

from enum import Enum


class DataClassification(str, Enum):
    """Sensitivity classification for a field or table."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, PHI, financial — strongest controls
