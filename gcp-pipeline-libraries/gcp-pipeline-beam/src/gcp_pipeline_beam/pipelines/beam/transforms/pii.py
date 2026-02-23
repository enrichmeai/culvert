"""
PII Masking Transforms

Beam DoFns for masking PII data in-flight based on EntitySchema metadata.
"""

import logging
from typing import Dict, Any, Iterator, TYPE_CHECKING, Optional

import apache_beam as beam

if TYPE_CHECKING:
    from gcp_pipeline_core.schema import EntitySchema

logger = logging.getLogger(__name__)


class MaskPIIDoFn(beam.DoFn):
    """
    In-flight PII masking transform.
    
    Automatically masks fields in a record based on the provided EntitySchema.
    Uses field.pii_type to determine the masking strategy.
    
    Supported Strategies (pii_type):
    - SSN: XXX-XX-last4
    - EMAIL: ****@domain.com
    - FULL / REDACTED: ***** / REDACTED
    - PARTIAL: masks all but last 4
    
    Example:
        >>> from application1.schema import EMCustomerSchema
        >>> masked = records | beam.ParDo(MaskPIIDoFn(EMCustomerSchema))
    """

    def __init__(self, schema: 'EntitySchema'):
        super().__init__()
        self.schema = schema
        self.pii_fields = []
        self.mask_count = beam.metrics.Metrics.counter("pii", "masked_records")

    def setup(self):
        """Identify PII fields from schema."""
        self.pii_fields = [f for f in self.schema.fields if f.is_pii]
        logger.info(f"Initialized MaskPIIDoFn with {len(self.pii_fields)} PII fields")

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Apply masking to the record."""
        if not self.pii_fields:
            yield element
            return

        masked_element = element.copy()
        is_masked = False

        for field in self.pii_fields:
            if field.name in masked_element and masked_element[field.name] is not None:
                original_value = masked_element[field.name]
                masked_element[field.name] = self._apply_mask(field, original_value)
                is_masked = True

        if is_masked:
            self.mask_count.inc()

        yield masked_element

    def _apply_mask(self, field, value: Any) -> Any:
        """Apply specific masking logic based on pii_type."""
        str_val = str(value)
        if not str_val:
            return value

        pii_type = (field.pii_type or "").upper()

        if pii_type == 'SSN':
            return f"XXX-XX-{str_val[-4:]}" if len(str_val) >= 4 else "XXX-XX-****"
        
        elif pii_type == 'EMAIL':
            if '@' in str_val:
                return "****" + str_val[str_val.find('@'):]
            return "****@****.***"
        
        elif pii_type == 'FULL':
            return "*" * len(str_val)
        
        elif pii_type == 'REDACTED':
            return "REDACTED"
        
        elif pii_type == 'PARTIAL':
            return "*" * (len(str_val) - 4) + str_val[-4:] if len(str_val) > 4 else "****"
        
        else:
            # Default fallback for PII=True but unknown/missing pii_type
            if len(str_val) > 4:
                return "*" * (len(str_val) - 4) + str_val[-4:]
            return "****"
