"""
Segment Transform Beam DoFns.

FormatFixedWidthDoFn: formats BigQuery rows to fixed-width strings
using a segment template loaded from YAML.
"""

import logging
from typing import Dict, Any

import apache_beam as beam

from ..config.models import SegmentTemplate
from ..formatting.formatters import format_record

logger = logging.getLogger(__name__)


class FormatFixedWidthDoFn(beam.DoFn):
    """
    Format BigQuery rows to fixed-width strings using a segment template.

    The template is stored as a plain dict for Beam serialisation and
    reconstructed in setup().
    """

    def __init__(self, template_dict: dict, extract_date: str):
        self._template_dict = template_dict
        self._extract_date = extract_date
        self._template = None
        self._records_formatted = beam.metrics.Metrics.counter(
            'segment_transform', 'records_formatted')
        self._format_errors = beam.metrics.Metrics.counter(
            'segment_transform', 'format_errors')

    def setup(self):
        self._template = SegmentTemplate.from_dict(self._template_dict)

    def process(self, row: Dict[str, Any]):
        context = {'extract_date': self._extract_date}
        try:
            line = format_record(row, self._template, context)
            self._records_formatted.inc()
            yield line
        except Exception as e:
            self._format_errors.inc()
            logger.warning(
                "Format error for row %s: %s",
                row.get('customer_id', '?'), e
            )
