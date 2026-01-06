"""
Pipeline Options Module

Defines GDWPipelineOptions for Beam pipeline command-line argument handling.
"""

from typing import Optional
from apache_beam.options.pipeline_options import PipelineOptions
import logging

logger = logging.getLogger(__name__)


class GDWPipelineOptions(PipelineOptions):
    """
    GDW-specific Pipeline Options.

    Extends Apache Beam's PipelineOptions with additional options specific
    to GDW migration pipelines, including input/output paths, credentials,
    and autoscaling settings.

    These options are passed as command-line arguments to the pipeline:
        python pipeline.py \\
            --input_pattern='gs://bucket/input/*.csv' \\
            --output_table='project.dataset.output' \\
            --error_table='project.dataset.errors' \\
            --run_id='run_20231225_001' \\
            --project='my-gcp-project' \\
            --num_workers=2 \\
            --autoscaling_algorithm='THROUGHPUT_BASED'

    Example:
        >>> options = GDWPipelineOptions([
        ...     '--input_pattern=gs://bucket/input/*.csv',
        ...     '--output_table=project.dataset.output',
        ...     '--run_id=run_20231225_001',
        ...     '--project=my-gcp-project'
        ... ])
        >>> print(options.input_pattern)
        gs://bucket/input/*.csv
    """

    @classmethod
    def _add_argparse_args(cls, parser):
        """
        Add GDW-specific command-line arguments to parser.

        Args:
            parser: ArgumentParser instance from PipelineOptions
        """
        # Input/Output path arguments (support value providers for streaming)
        parser.add_value_provider_argument(
            '--input_pattern',
            type=str,
            default='',
            help='Input file pattern (e.g., gs://bucket/input/*.csv)'
        )

        parser.add_value_provider_argument(
            '--output_table',
            type=str,
            default='',
            help='Output BigQuery table (e.g., project.dataset.table)'
        )

        parser.add_value_provider_argument(
            '--error_table',
            type=str,
            default='',
            help='Error BigQuery table for failed records (e.g., project.dataset.errors)'
        )

        # Run tracking
        parser.add_value_provider_argument(
            '--run_id',
            type=str,
            default='',
            help='Unique run identifier for tracking and auditing'
        )

        # GCP Configuration
        parser.add_value_provider_argument(
            '--project',
            type=str,
            default='',
            help='GCP Project ID for resources'
        )

        # Autoscaling and worker configuration
        parser.add_argument(
            '--autoscaling_algorithm',
            type=str,
            default='THROUGHPUT_BASED',
            choices=['THROUGHPUT_BASED', 'NONE'],
            help='Autoscaling algorithm: THROUGHPUT_BASED (scale with load) or NONE (fixed workers)'
        )

        parser.add_argument(
            '--num_workers',
            type=int,
            default=1,
            help='Number of worker machines (used when autoscaling_algorithm=NONE)'
        )

        # Additional configuration
        parser.add_argument(
            '--max_num_workers',
            type=int,
            default=10,
            help='Maximum number of worker machines when autoscaling is enabled'
        )

        parser.add_argument(
            '--batch_size',
            type=int,
            default=1000,
            help='Batch size for I/O operations'
        )

