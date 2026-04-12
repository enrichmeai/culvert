"""
Mainframe Segment Pipeline.

Template-driven Apache Beam pipeline that reads BigQuery data (typically
the CDP snapshot layer) via a SQL query and produces fixed-width segment
files in GCS.

Designed for 25 GB+ monthly extracts:
  - DIRECT_READ method avoids temporary GCS export
  - Controlled sharding via max_records_per_shard (default 1M rows ~ 500 MB)
  - Manifest file with record counts for mainframe verification
"""

import json
import logging

import apache_beam as beam
from gcp_pipeline_beam.pipelines.base.pipeline import BasePipeline

from ..config.models import SegmentTemplate
from .transforms import FormatFixedWidthDoFn

logger = logging.getLogger(__name__)


class MainframeSegmentPipeline(BasePipeline):
    """
    Template-driven mainframe segment export pipeline.

    For each segment:
      1. Execute the SQL query from the template against BigQuery
      2. Format each row to a fixed-width record using the output template
      3. Write sharded segment files to GCS
      4. Write a manifest file with record counts
    """

    def __init__(self, options, config, template: SegmentTemplate,
                 output_bucket: str, extract_date: str,
                 period_start: str = '', period_end: str = '',
                 extract_month: str = '', fdp_project: str = ''):
        super().__init__(options, config)
        self.template = template
        self.output_bucket = output_bucket
        self.extract_date = extract_date
        self.period_start = period_start
        self.period_end = period_end
        self.extract_month = extract_month
        # FDP source project (defaults to gcp_project_id for same-project reads)
        self.fdp_project = fdp_project or config.gcp_project_id

    def build(self, pipeline: beam.Pipeline):
        """Define the segment export pipeline DAG."""
        project = self.config.gcp_project_id
        run_id = self.config.run_id

        # Resolve placeholders in the SQL query.
        # {project} refers to the FDP source project (cross-project for FDP reads,
        # same-project for legacy CDP reads). Defaults to the Dataflow-running
        # project if --fdp_project is not specified.
        query = self.template.query.format(
            project=self.fdp_project,
            period_start=self.period_start,
            period_end=self.period_end,
        )

        logger.info(
            "Reading from BigQuery: %s.%s (segment=%s, period=%s to %s)",
            self.template.source.dataset,
            self.template.source.table,
            self.template.segment_id,
            self.period_start,
            self.period_end,
        )

        # Step 1: Execute SQL query via DIRECT_READ (no temp GCS export)
        rows = (
            pipeline
            | 'ReadCDP' >> beam.io.ReadFromBigQuery(
                query=query,
                use_standard_sql=True,
                project=project,
                method=beam.io.ReadFromBigQuery.Method.DIRECT_READ,
            )
        )

        # Step 2: Format rows to fixed-width strings
        output_config = self.template.output
        period_label = self.extract_month or self.extract_date[:6]
        output_dir = (
            f"gs://{self.output_bucket}/segments/{period_label}/"
            f"{run_id}/{self.template.segment_id}"
        )
        output_prefix = f"{output_dir}/{output_config.file_prefix}"

        formatted = (
            rows
            | 'FormatFixedWidth' >> beam.ParDo(
                FormatFixedWidthDoFn(
                    self.template.to_dict(),
                    self.extract_date,
                )
            )
        )

        # Step 3: Write sharded segment files
        write_kwargs = {
            'file_name_suffix': output_config.file_suffix,
            'shard_name_template': output_config.shard_template,
        }
        if output_config.max_records_per_shard > 0:
            write_kwargs['max_records_per_shard'] = (
                output_config.max_records_per_shard
            )

        formatted | 'WriteSegmentFiles' >> beam.io.WriteToText(
            output_prefix,
            **write_kwargs,
        )

        # Step 4: Count records and write manifest
        record_count = (
            formatted
            | 'CountRecords' >> beam.combiners.Count.Globally()
        )

        manifest_path = f"{output_dir}/{output_config.file_prefix}.manifest"
        (
            record_count
            | 'BuildManifest' >> beam.Map(
                _build_manifest,
                segment_id=self.template.segment_id,
                period=period_label,
                run_id=run_id,
                extract_date=self.extract_date,
                file_prefix=output_config.file_prefix,
                file_suffix=output_config.file_suffix,
                record_length=self.template.record_length,
                max_records_per_shard=output_config.max_records_per_shard,
            )
            | 'WriteManifest' >> beam.io.WriteToText(
                manifest_path,
                shard_name_template='',
                file_name_suffix='',
            )
        )

        logger.info(
            "Segment '%s' will write to: %s*%s (manifest: %s)",
            self.template.segment_id,
            output_prefix,
            output_config.file_suffix,
            manifest_path,
        )


MANIFEST_REQUIRED_KEYS = frozenset({
    'segment', 'period', 'run_id', 'extract_date',
    'total_records', 'record_length', 'num_shards',
    'max_records_per_shard', 'file_pattern',
})


def _build_manifest(total_records: int, segment_id: str, period: str,
                    run_id: str, extract_date: str, file_prefix: str,
                    file_suffix: str, record_length: int,
                    max_records_per_shard: int) -> str:
    """Build a JSON manifest string from the record count.

    Validates that all required keys are present and total_records is
    non-negative before serialising.
    """
    import math

    if total_records < 0:
        raise ValueError(
            f"Manifest total_records must be non-negative, got {total_records}"
        )

    num_shards = (
        math.ceil(total_records / max_records_per_shard)
        if max_records_per_shard > 0 else 1
    )
    manifest = {
        'segment': segment_id,
        'period': period,
        'run_id': run_id,
        'extract_date': extract_date,
        'total_records': total_records,
        'record_length': record_length,
        'num_shards': num_shards,
        'max_records_per_shard': max_records_per_shard,
        'file_pattern': f"{file_prefix}-*-of-*{file_suffix}",
    }

    missing = MANIFEST_REQUIRED_KEYS - set(manifest.keys())
    if missing:
        raise ValueError(f"Manifest missing required keys: {sorted(missing)}")

    return json.dumps(manifest, indent=2)
