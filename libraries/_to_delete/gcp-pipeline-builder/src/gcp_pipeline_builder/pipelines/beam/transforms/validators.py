"""
Validators Module

Record validation DoFns for Apache Beam pipelines.
Supports both custom validation functions and schema-driven validation.
"""

import logging
from typing import Dict, Any, Callable, Iterator, Optional, List, TYPE_CHECKING

import apache_beam as beam

if TYPE_CHECKING:
    from ....schema import EntitySchema

logger = logging.getLogger(__name__)


class ValidateRecordDoFn(beam.DoFn):
    """
    Validates records using a validation function.

    Routes valid records to main output and invalid records with errors
    to 'invalid' output tag. Supports custom validation logic via callable.
    """

    def __init__(self, validation_fn: Callable[[Dict[str, Any]], list]):
        super().__init__()
        self.validation_fn = validation_fn
        self.valid_records = beam.metrics.Metrics.counter("validate", "valid")
        self.invalid_records = beam.metrics.Metrics.counter("validate", "invalid")

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        try:
            errors = self.validation_fn(element)

            if errors:
                logger.warning(f"Validation failed for record: {errors}")
                self.invalid_records.inc()
                yield beam.pvalue.TaggedOutput('invalid', {
                    'errors': errors,
                    'record': element
                })
            else:
                self.valid_records.inc()
                yield element

        except Exception as e:
            logger.error(f"Error validating record: {e}")
            self.invalid_records.inc()
            yield beam.pvalue.TaggedOutput('invalid', {
                'error': str(e),
                'record': element
            })


class SchemaValidateRecordDoFn(beam.DoFn):
    """
    Schema-driven record validator.

    Validates records automatically based on EntitySchema definition.
    No custom validation code needed - schema defines everything.

    Features:
    - Required field checking
    - Allowed values validation
    - Max length validation
    - Type checking (INTEGER, NUMERIC, DATE, etc.)
    - PII masking in error output

    Example:
        >>> from em.schema import EMCustomerSchema
        >>> validator = SchemaValidateRecordDoFn(EMCustomerSchema)
        >>> validated = records | beam.ParDo(validator).with_outputs('invalid')
    """

    def __init__(
        self,
        schema: 'EntitySchema',
        custom_validators: Optional[Dict[str, Callable[[Any], List[str]]]] = None
    ):
        super().__init__()
        self.schema = schema
        self.custom_validators = custom_validators
        self._validator = None
        self.valid_records = beam.metrics.Metrics.counter("validate", "valid")
        self.invalid_records = beam.metrics.Metrics.counter("validate", "invalid")

    def setup(self):
        """Set up schema validator (called once per worker)."""
        from ....validators import SchemaValidator
        self._validator = SchemaValidator(
            schema=self.schema,
            custom_validators=self.custom_validators
        )

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        try:
            errors = self._validator.validate(element)
            error_strings = [str(e) for e in errors]

            if error_strings:
                logger.warning(f"Validation failed for record: {error_strings}")
                self.invalid_records.inc()
                yield beam.pvalue.TaggedOutput('invalid', {
                    'errors': error_strings,
                    'record': element
                })
            else:
                self.valid_records.inc()
                yield element

        except Exception as e:
            logger.error(f"Error validating record: {e}")
            self.invalid_records.inc()
            yield beam.pvalue.TaggedOutput('invalid', {
                'error': str(e),
                'record': element
            })


__all__ = ['ValidateRecordDoFn', 'SchemaValidateRecordDoFn']
