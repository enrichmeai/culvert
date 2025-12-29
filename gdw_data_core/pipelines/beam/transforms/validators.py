"""
Validators Module

Record validation DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Callable, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class ValidateRecordDoFn(beam.DoFn):
    """
    Validates records using a validation function.

    Routes valid records to main output and invalid records with errors
    to 'invalid' output tag. Supports custom validation logic via callable.

    Attributes:
        validation_fn: Callable that returns list of errors (empty if valid)

    Outputs:
        Main: Dict[str, Any] - Valid records
        'invalid': Dict - Invalid records with error information

    Metrics:
        validate/valid: Counter of valid records
        validate/invalid: Counter of invalid records

    Example:
        >>> def validate_record(record):
        ...     errors = []
        ...     if not record.get('id'):
        ...         errors.append('Missing required field: id')
        ...     if not record.get('email') or '@' not in record['email']:
        ...         errors.append('Invalid email format')
        ...     return errors
        >>>
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'email']))
        ...         | 'Validate' >> beam.ParDo(
        ...             ValidateRecordDoFn(validate_record)
        ...         ).with_outputs('main', 'invalid')
    """

    def __init__(self, validation_fn: Callable[[Dict[str, Any]], list]):
        """
        Initialize record validator.

        Args:
            validation_fn: Function that takes a record dict and returns
                          a list of error strings (empty if valid)

        Example:
            >>> def my_validator(record):
            ...     return [] if record.get('id') else ['Missing id']
            >>>
            >>> validator = ValidateRecordDoFn(my_validator)
        """
        super().__init__()
        self.validation_fn = validation_fn
        self.valid_records = beam.metrics.Metrics.counter("validate", "valid")
        self.invalid_records = beam.metrics.Metrics.counter("validate", "invalid")

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """
        Validate record and route to appropriate output.

        Args:
            element: Record to validate

        Yields:
            Dict: If valid, yields to main output
            TaggedOutput('invalid', ...): If invalid, with error details

        Example:
            >>> validator = ValidateRecordDoFn(lambda r: [] if r else ['Empty record'])
            >>> list(validator.process({'id': '1', 'name': 'John'}))
            [{'id': '1', 'name': 'John'}]

            >>> list(validator.process({}))
            [TaggedOutput('invalid', {'errors': ['Empty record'], ...})]
        """
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

