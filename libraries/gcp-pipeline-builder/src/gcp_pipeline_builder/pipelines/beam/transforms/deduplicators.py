"""
Deduplicators Module

Record deduplication DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Callable, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class DeduplicateRecordsDoFn(beam.DoFn):
    """
    Removes duplicate records based on a key function.

    Tracks seen records using a key function and filters out duplicates.
    Useful for deduplication before writing to databases or when merging
    data from multiple sources.

    Note: Key tracking is per-worker. For global deduplication in distributed
    environments, consider using Beam's built-in deduplication or grouping.

    Attributes:
        key_fn: Callable that extracts the deduplication key from a record

    Outputs:
        Main: Dict[str, Any] - Unique records (first occurrence)
        'duplicates': Dict - Duplicate records (filtered out)

    Metrics:
        dedup/unique: Counter of unique records passed through
        dedup/duplicates: Counter of duplicate records filtered

    Example:
        >>> # Deduplicate by ID
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'name']))
        ...         | 'Deduplicate' >> beam.ParDo(DeduplicateRecordsDoFn(
        ...             key_fn=lambda r: r.get('id')
        ...         )).with_outputs('main', 'duplicates')
        >>>
        >>> # Deduplicate by composite key
        >>> pipeline | 'Dedup' >> beam.ParDo(DeduplicateRecordsDoFn(
        ...     key_fn=lambda r: (r['user_id'], r['transaction_date'])
        ... ))
    """

    def __init__(self, key_fn: Callable[[Dict[str, Any]], Any]):
        """
        Initialize record deduplicator.

        Args:
            key_fn: Function that takes a record and returns the deduplication key

        Example:
            >>> # Simple key function
            >>> dedup = DeduplicateRecordsDoFn(key_fn=lambda r: r['id'])
            >>>
            >>> # Composite key function
            >>> dedup = DeduplicateRecordsDoFn(
            ...     key_fn=lambda r: (r['user_id'], r['date'])
            ... )
        """
        super().__init__()
        self.key_fn = key_fn
        self.seen_keys = set()
        self.unique = beam.metrics.Metrics.counter("dedup", "unique")
        self.duplicates = beam.metrics.Metrics.counter("dedup", "duplicates")

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """
        Filter duplicate records based on key function.

        Args:
            element: Record to check

        Yields:
            Dict: If first occurrence of key
            TaggedOutput('duplicates', ...): If duplicate

        Example:
            >>> dedup = DeduplicateRecordsDoFn(key_fn=lambda r: r['id'])
            >>>
            >>> # First record with id=1 passes
            >>> list(dedup.process({'id': '1', 'name': 'John'}))
            [{'id': '1', 'name': 'John'}]
            >>>
            >>> # Second record with id=1 is filtered
            >>> list(dedup.process({'id': '1', 'name': 'Jonathan'}))
            [TaggedOutput('duplicates', {'id': '1', 'name': 'Jonathan'})]
        """
        try:
            key = self.key_fn(element)

            if key not in self.seen_keys:
                self.seen_keys.add(key)
                self.unique.inc()
                yield element
            else:
                logger.debug(f"Skipped duplicate record with key: {key}")
                self.duplicates.inc()
                yield beam.pvalue.TaggedOutput('duplicates', element)

        except Exception as e:
            logger.error(f"Error deduplicating record: {e}")
            # Yield original element on error to avoid data loss
            self.unique.inc()
            yield element

