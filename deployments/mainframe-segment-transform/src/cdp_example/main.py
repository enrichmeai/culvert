"""
Mainframe Segment Transform Pipeline

Reads the CDP table `cdp_generic.customer_risk_profile` from BigQuery and
produces fixed-width segment files in GCS for downstream mainframe consumption.

Each output segment file contains one record per line in the format:
  <SEGMENT_TYPE><CUSTOMER_ID><ACCOUNT_ID><BALANCE><RISK_SCORE><SEGMENT_CODE><EXTRACT_DATE>
  (fixed-width, 200 chars per line, space-padded)

Output path pattern:
  gs://{bucket}/segments/{run_id}/{cdp_segment}/segment_{shard}.txt

Usage:
    python main.py \\
        --project joseph-antony-aruja \\
        --cdp_dataset cdp_generic \\
        --cdp_table customer_risk_profile \\
        --output_bucket joseph-antony-aruja-generic-dev-segments \\
        --run_id manual_20260311_001 \\
        --runner DirectRunner
"""

import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed-width field widths (total = 200 chars)
FIELD_WIDTHS = {
    'segment_type':      4,   # e.g. "ACTI", "DECL", "REFR", "PEND"
    'customer_id':      20,
    'account_id':       20,
    'current_balance':  15,   # right-justified, 2dp, e.g. "      12345.67"
    'risk_score':        6,   # right-justified integer
    'decision_outcome': 10,   # APPROVED / DECLINED / REFERRED / UNKNOWN
    'facility_status':  12,   # application_status
    'loan_amount':      15,   # right-justified, 2dp
    'interest_rate':     8,   # right-justified, 4dp e.g. "  5.2500"
    'term_months':       4,   # right-justified
    'cdp_segment':      20,
    'extract_date':      8,   # YYYYMMDD
    'filler':           58,   # reserved / padding
}

assert sum(FIELD_WIDTHS.values()) == 200, "Segment record must be exactly 200 chars"

SEGMENT_TYPE_MAP = {
    'ACTIVE_APPROVED': 'ACTI',
    'DECLINED':        'DECL',
    'REFERRED':        'REFR',
    'PENDING':         'PEND',
}


def _pad_left(value: Any, width: int, fill: str = ' ') -> str:
    """Right-justify (left-pad) a value to the given width."""
    return str(value or '').strip()[:width].rjust(width, fill)


def _pad_right(value: Any, width: int) -> str:
    """Left-justify (right-pad) a value to the given width."""
    return str(value or '').strip()[:width].ljust(width)


def _fmt_amount(value: Any, width: int) -> str:
    """Format a monetary amount to 2dp, right-justified."""
    try:
        return _pad_left(f'{float(value):.2f}', width)
    except (TypeError, ValueError):
        return _pad_left('0.00', width)


def _fmt_rate(value: Any) -> str:
    """Format interest rate to 4dp, right-justified in 8 chars."""
    try:
        return _pad_left(f'{float(value):.4f}', FIELD_WIDTHS['interest_rate'])
    except (TypeError, ValueError):
        return _pad_left('0.0000', FIELD_WIDTHS['interest_rate'])


def _extract_date_str(extract_date: Any) -> str:
    """Convert extract_date (DATE / str) to YYYYMMDD string."""
    if extract_date is None:
        return '00000000'
    s = str(extract_date).replace('-', '')[:8]
    return s.ljust(8, '0')


def format_segment_record(row: Dict[str, Any]) -> str:
    """
    Convert a cdp_generic.customer_risk_profile row to a 200-char fixed-width line.
    """
    cdp_segment = str(row.get('cdp_segment') or 'PENDING')
    segment_type = SEGMENT_TYPE_MAP.get(cdp_segment, 'PEND')

    line = (
        _pad_right(segment_type,                    FIELD_WIDTHS['segment_type'])
        + _pad_right(row.get('customer_id'),         FIELD_WIDTHS['customer_id'])
        + _pad_right(row.get('account_id'),          FIELD_WIDTHS['account_id'])
        + _fmt_amount(row.get('current_balance'), FIELD_WIDTHS['current_balance'])
        + _pad_left(row.get('risk_score') or '0',    FIELD_WIDTHS['risk_score'])
        + _pad_right(row.get('decision_outcome'),    FIELD_WIDTHS['decision_outcome'])
        + _pad_right(row.get('facility_status'),     FIELD_WIDTHS['facility_status'])
        + _fmt_amount(row.get('loan_amount'),     FIELD_WIDTHS['loan_amount'])
        + _fmt_rate(row.get('interest_rate'))
        + _pad_left(row.get('term_months') or '0',   FIELD_WIDTHS['term_months'])
        + _pad_right(cdp_segment,                    FIELD_WIDTHS['cdp_segment'])
        + _extract_date_str(row.get('_extract_date'))
        + ' ' * FIELD_WIDTHS['filler']
    )
    assert len(line) == 200, f"Segment line length {len(line)} != 200 for customer {row.get('customer_id')}"
    return line


class SegmentByCategory(beam.DoFn):
    """Emit (cdp_segment, formatted_line) tuples for downstream routing."""

    def process(self, row: Dict[str, Any]):
        segment = str(row.get('cdp_segment') or 'PENDING')
        line = format_segment_record(row)
        yield segment, line


def run_segment_pipeline(
    project_id: str,
    cdp_dataset: str,
    cdp_table: str,
    output_bucket: str,
    run_id: str,
    pipeline_args: Optional[list] = None,
):
    """
    Build and run the mainframe segment export pipeline.

    Reads cdp_generic.customer_risk_profile and writes per-segment text files
    to GCS under gs://{output_bucket}/segments/{run_id}/{segment_category}/
    """
    logger.info("Starting mainframe segment export — run_id=%s", run_id)

    bq_table = f"{project_id}:{cdp_dataset}.{cdp_table}"

    options = PipelineOptions(
        pipeline_args or [],
        project=project_id,
        job_name=f"mainframe-segment-export-{run_id.lower().replace('_', '-')}",
    )

    with beam.Pipeline(options=options) as pipeline:

        rows = (
            pipeline
            | 'ReadCDPTable' >> beam.io.ReadFromBigQuery(
                table=bq_table,
                use_standard_sql=True,
            )
        )

        # Route each row into (segment_category, formatted_line)
        segment_lines = rows | 'FormatSegments' >> beam.ParDo(SegmentByCategory())

        # Write one file set per CDP segment category
        for segment_category in ['ACTIVE_APPROVED', 'DECLINED', 'REFERRED', 'PENDING']:
            output_prefix = (
                f"gs://{output_bucket}/segments/{run_id}/{segment_category}/segment"
            )
            (
                segment_lines
                | f'Filter_{segment_category}' >> beam.Filter(
                    lambda kv, cat=segment_category: kv[0] == cat
                )
                | f'ExtractLines_{segment_category}' >> beam.Map(lambda kv: kv[1])
                | f'WriteSegments_{segment_category}' >> beam.io.WriteToText(
                    output_prefix,
                    file_name_suffix='.txt',
                    shard_name_template='-SS-of-NN',
                )
            )

    logger.info("Mainframe segment export complete — run_id=%s", run_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mainframe Segment Transform Pipeline')
    parser.add_argument('--project',     required=True,  help='GCP Project ID')
    parser.add_argument('--cdp_dataset', default='cdp_generic', help='CDP BigQuery dataset')
    parser.add_argument('--cdp_table',   default='customer_risk_profile', help='CDP table name')
    parser.add_argument('--output_bucket', required=True, help='GCS bucket for segment files')
    parser.add_argument('--run_id',
                        default=f"run_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                        help='Unique run identifier')

    # Remaining args passed through to Beam PipelineOptions (runner, region, temp, etc.)
    known_args, pipeline_args = parser.parse_known_args()

    run_segment_pipeline(
        project_id=known_args.project,
        cdp_dataset=known_args.cdp_dataset,
        cdp_table=known_args.cdp_table,
        output_bucket=known_args.output_bucket,
        run_id=known_args.run_id,
        pipeline_args=pipeline_args,
    )
