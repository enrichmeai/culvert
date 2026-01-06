"""
Transformers Module

Record transformation DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Callable, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class TransformRecordDoFn(beam.DoFn):
    """
    Transforms records using a transformation function.

    Applies a custom transformation to each record, routing transformation
    errors to 'errors' output. Used for field mapping, value conversion,
    and data enrichment.

    Attributes:
        transform_fn: Callable that takes a record and returns transformed record

    Outputs:
        Main: Dict[str, Any] - Transformed records
        'errors': Dict - Records with transformation errors

    Metrics:
        transform/success: Counter of successful transformations
        transform/errors: Counter of transformation errors

    Example:
        >>> def enrich_record(record):
        ...     return {
        ...         **record,
        ...         'processed_at': datetime.utcnow().isoformat(),
        ...         'name': record.get('name', '').upper()
        ...     }
        >>>
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'name']))
        ...         | 'Transform' >> beam.ParDo(
        ...             TransformRecordDoFn(enrich_record)
        ...         ).with_outputs('main', 'errors')
    """

    def __init__(self, transform_fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """
        Initialize record transformer.

        Args:
            transform_fn: Function that takes a record dict and returns transformed dict

        Example:
            >>> def add_timestamp(record):
            ...     return {**record, 'timestamp': datetime.now().isoformat()}
            >>>
            >>> transformer = TransformRecordDoFn(add_timestamp)
        """
        super().__init__()
        self.transform_fn = transform_fn
        self.success = beam.metrics.Metrics.counter("transform", "success")
        self.errors = beam.metrics.Metrics.counter("transform", "errors")

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """
        Transform record using the transformation function.

        Args:
            element: Record to transform

        Yields:
            Dict: Transformed record if successful
            TaggedOutput('errors', ...): Error record if transformation fails

        Example:
            >>> def double_score(record):
            ...     return {**record, 'score': record['score'] * 2}
            >>>
            >>> transformer = TransformRecordDoFn(double_score)
            >>> list(transformer.process({'score': 50}))
            [{'score': 100}]
        """
        try:
            transformed = self.transform_fn(element)
            self.success.inc()
            yield transformed
        except Exception as e:
            logger.error(f"Error transforming record: {e}")
            self.errors.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'error': str(e),
                'record': element
            })

