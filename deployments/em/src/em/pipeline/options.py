"""
EM Pipeline Options.

Apache Beam pipeline options for EM entity processing.
"""

from apache_beam.options.pipeline_options import PipelineOptions


class EMPipelineOptions(PipelineOptions):
    """EM-specific pipeline options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--entity',
            type=str,
            required=True,
            choices=['customers', 'accounts', 'decision'],
            help='EM entity to process'
        )
        parser.add_argument(
            '--input_file',
            type=str,
            required=True,
            help='GCS path to input file'
        )
        parser.add_argument(
            '--output_table',
            type=str,
            required=True,
            help='BigQuery output table (project:dataset.table)'
        )
        parser.add_argument(
            '--error_table',
            type=str,
            required=True,
            help='BigQuery error table (project:dataset.table)'
        )
        parser.add_argument(
            '--run_id',
            type=str,
            required=True,
            help='Pipeline run ID'
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
            help='Project for job control table'
        )

