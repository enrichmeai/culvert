"""
Enrichers Module

Record enrichment DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Iterator
from datetime import datetime

import apache_beam as beam

logger = logging.getLogger(__name__)


class EnrichWithMetadataDoFn(beam.DoFn):
    """
    Enriches records with pipeline metadata.

    Adds metadata fields to each record such as run_id, pipeline_name,
    and processing timestamp. Useful for tracking, auditing, and debugging.

    Attributes:
        run_id: Unique pipeline run identifier
        pipeline_name: Name of the pipeline
        **metadata: Additional metadata key-value pairs to add to records

    Outputs:
        Main: Dict[str, Any] - Enriched records with metadata

    Example:
        >>> pipeline | 'ReadText' >> beam.io.ReadFromText('input.csv')
        ...         | 'ParseCSV' >> beam.ParDo(ParseCsvLine(['id', 'name']))
        ...         | 'Enrich' >> beam.ParDo(EnrichWithMetadataDoFn(
        ...             run_id='run_20231225_001',
        ...             pipeline_name='loa_applications',
        ...             environment='production'
        ...         ))
    """

    def __init__(self, run_id: str, pipeline_name: str, **metadata: Any):
        """
        Initialize metadata enricher.

        Args:
            run_id: Unique identifier for this pipeline run
            pipeline_name: Name of the pipeline
            **metadata: Additional metadata fields to add to records

        Example:
            >>> enricher = EnrichWithMetadataDoFn(
            ...     run_id='run_001',
            ...     pipeline_name='my_pipeline',
            ...     environment='prod',
            ...     version='1.0'
            ... )
        """
        super().__init__()
        self.run_id = run_id
        self.pipeline_name = pipeline_name
        self.metadata = metadata

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Add audit metadata to record.

        Args:
            element: Record to enrich

        Yields:
            Dict: Enriched record with added metadata fields (_run_id, _processed_at)

        Example:
            >>> enricher = EnrichWithMetadataDoFn(run_id='run_001', pipeline_name='test')
            >>> result = list(enricher.process({'id': '1', 'name': 'John'}))
            >>> enriched = result[0]
            >>> enriched['_run_id']
            'run_001'
            >>> enriched['pipeline_name']
            'test'
            >>> '_processed_at' in enriched
            True
        """
        enriched = {
            **element,
            '_run_id': self.run_id,
            'pipeline_name': self.pipeline_name,
            '_processed_at': datetime.utcnow().isoformat(),
            **self.metadata
        }
        yield enriched

