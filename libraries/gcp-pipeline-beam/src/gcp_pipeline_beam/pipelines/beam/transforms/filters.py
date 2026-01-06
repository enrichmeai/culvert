"""
Filters Module

Record filtering DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Callable, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class FilterRecordsDoFn(beam.DoFn):
    """
    Filters records based on a predicate function.

    Yields records where the predicate returns True, filtering out
    all other records. Useful for data quality filtering and subset selection.

    Attributes:
        predicate_fn: Callable that returns boolean (True to keep, False to filter)

    Outputs:
        Main: Dict[str, Any] - Records that pass the filter

    Metrics:
        filter/passed: Counter of records that passed filter
        filter/filtered: Counter of records that failed filter

    Example:
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'status']))
        ...         | 'FilterActive' >> beam.ParDo(FilterRecordsDoFn(
        ...             lambda r: r.get('status') == 'active'
        ...         ))
    """

    def __init__(self, predicate_fn: Callable[[Dict[str, Any]], bool]):
        """
        Initialize record filter.

        Args:
            predicate_fn: Function that takes a record and returns True to keep

        Example:
            >>> # Keep only active records
            >>> filter_fn = lambda r: r.get('status') == 'active'
            >>> filter_transform = FilterRecordsDoFn(filter_fn)
        """
        super().__init__()
        self.predicate_fn = predicate_fn
        self.passed = beam.metrics.Metrics.counter("filter", "passed")
        self.filtered = beam.metrics.Metrics.counter("filter", "filtered")

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Filter element based on predicate function.

        Args:
            element: Record to filter

        Yields:
            Dict: If predicate returns True

        Example:
            >>> filter_fn = lambda r: r['score'] > 80
            >>> filter_transform = FilterRecordsDoFn(filter_fn)
            >>> list(filter_transform.process({'score': 85}))
            [{'score': 85}]

            >>> list(filter_transform.process({'score': 75}))
            []
        """
        try:
            if self.predicate_fn(element):
                self.passed.inc()
                yield element
            else:
                self.filtered.inc()
        except Exception as e:
            logger.error(f"Error filtering record: {e}")
            self.filtered.inc()

