"""
Segment Transform Pipeline Options.

Apache Beam pipeline options for mainframe segment transform.

NOTE: output_table, error_table, run_id, and gcp_project are inherited from
gcp_pipeline_beam.GCPPipelineOptions and must not be redefined here.
"""

from apache_beam.options.pipeline_options import PipelineOptions


class SegmentTransformOptions(PipelineOptions):
    """Segment-transform-specific pipeline options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--segment',
            type=str,
            required=True,
            help='Segment ID to process (customer, credit_card, '
                 'check_debit_card, loans, savings)'
        )
        parser.add_argument(
            '--extract_date',
            type=str,
            required=True,
            help='Extract date in YYYYMMDD format'
        )
        parser.add_argument(
            '--extract_month',
            type=str,
            default='',
            help='Extract month in YYYYMM format. When set, the query '
                 'placeholders {period_start} and {period_end} are resolved '
                 'to the first and last day of the month (inclusive). '
                 'Defaults to the month of --extract_date if omitted.'
        )
        parser.add_argument(
            '--output_bucket',
            type=str,
            required=True,
            help='GCS bucket for output segment files'
        )
        parser.add_argument(
            '--config_dir',
            type=str,
            default='',
            help='Override path to config directory (default: bundled config/)'
        )
        parser.add_argument(
            '--fdp_project',
            type=str,
            default='',
            help='Producing teams GCP project containing the FDP source tables. '
                 'Used to resolve the {project} placeholder in segment template '
                 'queries. Defaults to --gcp_project if not specified (same-project '
                 'reads).'
        )
