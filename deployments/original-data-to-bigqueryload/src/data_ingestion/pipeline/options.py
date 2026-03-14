"""
Generic Pipeline Options.

Apache Beam pipeline options for Generic entity processing.

NOTE: output_table, error_table, and run_id are inherited from
gcp_pipeline_beam.GCPPipelineOptions and must not be redefined here.
"""

from apache_beam.options.pipeline_options import PipelineOptions


class GenericPipelineOptions(PipelineOptions):
    """Generic-specific pipeline options (entity, source file, extract date)."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--entity',
            type=str,
            required=True,
            choices=['customers', 'accounts', 'decision', 'applications'],
            help='Generic entity to process'
        )
        parser.add_argument(
            '--source_file',
            type=str,
            required=True,
            help='GCS path to input CSV file'
        )
        parser.add_argument(
            '--extract_date',
            type=str,
            required=True,
            help='Extract date (YYYYMMDD)'
        )
        parser.add_argument(
            '--job_control_project',
            type=str,
            default='',
            help='Project for job control table (defaults to --project)'
        )
