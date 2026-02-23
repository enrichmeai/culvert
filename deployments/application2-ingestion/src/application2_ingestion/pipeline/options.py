"""
Application2 Pipeline Options.

Command-line options for Application2 Beam pipelines.
"""

from apache_beam.options.pipeline_options import PipelineOptions


class LOAPipelineOptions(PipelineOptions):
    """Application2 Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        """Add Application2-specific arguments."""
        parser.add_argument(
            '--entity',
            type=str,
            required=True,
            choices=['applications'],
            help='Entity to process (applications)'
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

