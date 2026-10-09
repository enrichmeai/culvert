"""DataClassification enum — the taxonomic levels for sensitive data.

The values follow the common four-tier model used by Dataplex, AWS
Macie, and Azure Purview. `@governed` (`data_pipeline_core.decorators`)
declares a table's classification with it and reports each field's
`GovernancePolicy.classify` value.
"""

from enum import Enum


class DataClassification(str, Enum):
    """Sensitivity classification for a field or table."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, PHI, financial — strongest controls
