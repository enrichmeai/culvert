"""
LOA Pipeline Options.

Command-line options for LOA Beam pipelines.
"""

from apache_beam.options.pipeline_options import PipelineOptions


class LOAPipelineOptions(PipelineOptions):
    """LOA Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        """Add LOA-specific arguments."""
        parser.add_argument(
            '--entity',
            type=str,
            required=True,
            choices=['applications'],
            help='Entity to process (applications)'
        )
        parser.add_argument(
            '--input_pattern',
            type=str,
            required=True,
            help='GCS pattern for input files (e.g., gs://bucket/loa/*.csv)'
        )
        parser.add_argument(
            '--output_table',
            type=str,
            required=True,
            help='BigQuery output table (e.g., project:odp_loa.applications)'
        )
        parser.add_argument(
            '--error_table',
            type=str,
            required=True,
            help='BigQuery error table (e.g., project:odp_loa.applications_errors)'
        )
        parser.add_argument(
            '--run_id',
            type=str,
            default=None,
            help='Pipeline run ID (auto-generated if not provided)'
        )
        parser.add_argument(
            '--project_id',
            type=str,
            required=True,
            help='GCP project ID'
        )
        parser.add_argument(
            '--extract_date',
            type=str,
            default=None,
            help='Extract date in YYYY-MM-DD format'
        )
        parser.add_argument(
            '--trigger_fdp',
            type=bool,
            default=True,
            help='Whether to trigger FDP transformation after ODP load (default: True)'
        )

