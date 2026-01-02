"""
LOA JCL Migration - Apache Beam/Dataflow Pipeline Template
============================================================

Purpose:
  Template for migrating JCL batch jobs to Apache Beam/Dataflow pipelines.
  This replaces mainframe JCL step execution with cloud-native batch processing.

Pattern:
  1. Read split files from GCS (handles applications_YYYYMMDD_1, _2, etc.)
  2. Parse CSV lines into dicts
  3. Validate each record
  4. Write valid records to BigQuery
  5. Write error records to error table
  6. Add metadata (run_id, processed_timestamp, source_file)

Usage:
  # Local testing with DirectRunner
  python loa_jcl_template.py --output_table project:dataset.applications

  # Production with Dataflow
  python loa_jcl_template.py \\
    --runner DataflowRunner \\
    --project my-project \\
    --region us-central1 \\
    --output_table my-project:loa_processed.applications

Design Notes:
  - Use DirectRunner for local testing
  - Use DataflowRunner for production
  - Beam handles split file discovery via wildcard patterns
  - Side outputs separate valid and error records
  - Metadata added in transformation step, not at source
"""

import logging
from typing import Dict, List, Any, Optional

import apache_beam as beam
from apache_beam.io import ReadFromText, WriteToBigQuery
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms import ParDo

# Import GDW Core Framework
from gdw_data_core.core.validators import ValidationError
from gdw_data_core.pipelines.base.pipeline import BasePipeline
from gdw_data_core.pipelines.base.options import GDWPipelineOptions
from gdw_data_core.pipelines.beam.transforms.validators import ValidateRecordDoFn
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext
from gdw_data_core.core.monitoring import MetricsCollector, HealthChecker
from gdw_data_core.core.audit import AuditTrail
from gdw_data_core.core.utilities import generate_run_id
from gdw_data_core.pipelines.beam.transforms.deduplicators import DeduplicateRecordsDoFn
from gdw_data_core.pipelines.beam.transforms.parsers import ParseCsvLine
from gdw_data_core.pipelines.beam.transforms.enrichers import EnrichWithMetadataDoFn

# Import LOA common modules
from blueprint.em.components.loa_domain.validation import (
    validate_application_record,
    validate_customer_record,
    validate_branch_record,
    validate_collateral_record
)
from blueprint.em.components.loa_domain.schema import (
    APPLICATIONS_RAW_SCHEMA,
    APPLICATIONS_ERROR_SCHEMA,
    BRANCHES_RAW_SCHEMA,
    CUSTOMERS_RAW_SCHEMA,
    COLLATERAL_RAW_SCHEMA,
)


logger = logging.getLogger(__name__)


# ============================================================================
# Validation Functions - Library Pattern
# ============================================================================

def validate_application_fn(record: Dict[str, Any]) -> List[ValidationError]:
    """Validate application record returning only errors.

    Demonstrates the GDW Data Core validation pattern: validation functions
    accept a record and return a list of ValidationError objects which are
    automatically processed by ValidateRecordDoFn.

    Args:
        record: Application record to validate

    Returns:
        List[ValidationError]: Empty if valid, otherwise list of errors

    Note:
        Library automatically handles:
        - PII masking in error values (SSN, phone, etc.)
        - Error classification (CRITICAL, WARNING, INFO)
        - Metrics emission
        - Error storage
    """
    validated, errors = validate_application_record(record)
    return errors


def validate_customer_fn(record: Dict[str, Any]) -> List[ValidationError]:
    """Validate customer record returning only errors."""
    validated, errors = validate_customer_record(record)
    return errors


def validate_branch_fn(record: Dict[str, Any]) -> List[ValidationError]:
    """Validate branch record returning only errors."""
    validated, errors = validate_branch_record(record)
    return errors


def validate_collateral_fn(record: Dict[str, Any]) -> List[ValidationError]:
    """Validate collateral record returning only errors."""
    validated, errors = validate_collateral_record(record)
    return errors


class AddMetadata(beam.DoFn):
    """Add enrichment metadata to record."""

    def process(self, record: Dict[str, str]) -> Any:
        """Add processing metadata and timestamps.

        Args:
            record: Record to enrich

        Yields:
            Enriched record with metadata
        """
        # Library's ValidateRecordDoFn already adds run_id and source_file
        # Here we can add additional enrichment as needed
        yield record


# ============================================================================
# Pipeline Class
# ============================================================================

class LOAJCLPipeline(BasePipeline):
    """LOA JCL Migration Pipeline.

    Reference implementation demonstrating:
    - ValidateRecordDoFn usage (not custom DoFn)
    - Library transforms for deduplication
    - Automatic error handling and metrics
    - Metadata enrichment

    Inherits from gdw_data_core.pipelines.BasePipeline.
    """

    def __init__(self, options: PipelineOptions, entity_type: str = "applications", config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize pipeline.

        Args:
            options: Pipeline options
            entity_type: Type of entity being processed
            config: Pipeline configuration
        """
        # Ensure config has necessary fields for BasePipeline
        if config is None:
            config = {}

        gdw_options = options.view_as(GDWPipelineOptions)
        run_id = gdw_options.run_id.get() or config.get('run_id') or generate_run_id(f"loa-{entity_type}")

        config.update({
            'run_id': run_id,
            'pipeline_name': f"loa-{entity_type}",
            'entity_type': entity_type,
            'source_file': gdw_options.input_pattern.get() or config.get('source_file', 'unknown')
        })

        super().__init__(options=options, config=config)
        self.entity_type = entity_type
        self.gdw_options = gdw_options

    def build(self, p: beam.Pipeline) -> None:
        """Build the LOA JCL pipeline with library transforms.

        Demonstrates the GDW Data Core pipeline pattern:
        - Uses ValidateRecordDoFn from library (not custom DoFn)
        - Uses DeduplicateRecordsDoFn from library
        - Metrics automatically emitted by library transforms
        - Error handling automatic via ErrorContext

        Args:
            p: Beam pipeline instance
        """
        input_pattern = self.gdw_options.input_pattern.get()
        output_table = self.gdw_options.output_table.get()
        error_table = self.gdw_options.error_table.get()
        run_id = self.gdw_options.run_id.get() or generate_run_id(f"loa-{self.entity_type}")

        # Schema mapping
        schema_map = {
            "applications": APPLICATIONS_RAW_SCHEMA,
            "branches": BRANCHES_RAW_SCHEMA,
            "customers": CUSTOMERS_RAW_SCHEMA,
            "collateral": COLLATERAL_RAW_SCHEMA
        }
        schema = schema_map.get(self.entity_type)

        # Default field names
        field_names = [f["name"] for f in schema if f["name"] not in ["run_id", "processed_timestamp", "source_file"]]

        # Validation function mapping
        validation_map = {
            "applications": validate_application_fn,
            "branches": validate_branch_fn,
            "customers": validate_customer_fn,
            "collateral": validate_collateral_fn
        }
        validation_fn = validation_map.get(self.entity_type)

        raw_records = p | f"Read {self.entity_type}" >> ReadFromText(input_pattern, skip_header_lines=1)
        parsed_records = raw_records | "Parse CSV" >> ParDo(ParseCsvLine(field_names))

        # Deduplicate
        key_fields = {
            "applications": "application_id",
            "customers": "customer_id",
            "branches": "branch_code",
            "collateral": "collateral_id"
        }

        deduplicated_results = (
            parsed_records
            | "Deduplicate" >> ParDo(DeduplicateRecordsDoFn(
                key_fn=lambda r: r.get(key_fields.get(self.entity_type))
            )).with_outputs('duplicates', main='main')
        )

        # Validate using library's ValidateRecordDoFn (replaces custom DoFn)
        # ValidateRecordDoFn automatically:
        # - Routes valid records to main output
        # - Routes error records to 'errors' output
        # - Emits metrics (validation_success, validation_errors)
        # - Adds run_id and source_file metadata
        # - Masks PII in error messages
        validation_results = (
            deduplicated_results['main']
            | f"Validate {self.entity_type}" >> ParDo(ValidateRecordDoFn(
                validation_fn=validation_fn,
                run_id=run_id,
                source_name=input_pattern
            )).with_outputs('errors', main='main')
        )

        # Write valid records
        _ = (
            validation_results['main']
            | "Enrich" >> ParDo(EnrichWithMetadataDoFn(
                run_id=run_id,
                pipeline_name=f"loa-{self.entity_type}"
            ))
            | f"Write Valid to {self.entity_type}" >> WriteToBigQuery(
                table=output_table,
                schema=schema,
                create_disposition="CREATE_IF_NEEDED",
                write_disposition="WRITE_APPEND"
            )
        )

        # Write error records
        _ = (
            validation_results['errors']
            | f"Write Errors for {self.entity_type}" >> WriteToBigQuery(
                table=error_table,
                schema=APPLICATIONS_ERROR_SCHEMA,
                create_disposition="CREATE_IF_NEEDED",
                write_disposition="WRITE_APPEND"
            )
        )


def run_pipeline(
    input_pattern: str,
    output_table: str,
    error_table: str,
    project: str,
    entity_type: str = "applications",
    region: str = "us-central1",
    run_id: Optional[str] = None,
    job_name: str = "loa-jcl-migration",
    runner: str = "DirectRunner",
    temp_location: Optional[str] = None,
) -> int:
    """Run LOA pipeline with error handling and metrics tracking.

    Demonstrates the GDW Data Core pipeline execution pattern:
    - Initializes ErrorHandler for error classification and tracking
    - Uses MetricsCollector for automatic metrics collection
    - Wraps execution in ErrorContext for error recovery
    - Provides unified error handling across pipeline execution

    Args:
        input_pattern: GCS wildcard pattern for input files
        output_table: BigQuery table for valid records
        error_table: BigQuery table for error records
        project: GCP project ID
        entity_type: Type of entity being processed
        region: GCP region
        run_id: Run identifier (generated if not provided)
        job_name: Beam job name
        runner: Beam runner (DirectRunner or DataflowRunner)
        temp_location: Temp location for Dataflow (required for DataflowRunner)

    Returns:
        int: Exit code (0 = success)

    Raises:
        Exception: If pipeline execution fails and all retry attempts exhausted
    """
    # Generate or use provided run_id
    execution_run_id = run_id or generate_run_id(f"loa-{entity_type}")

    # Initialize error handler
    error_handler = ErrorHandler(
        pipeline_name=f"loa-{entity_type}",
        run_id=execution_run_id,
        max_retries=3
    )

    # Initialize metrics collector
    metrics_collector = MetricsCollector(
        pipeline_name=f"loa-{entity_type}",
        run_id=execution_run_id
    )

    # Initialize audit trail
    audit = AuditTrail(
        run_id=execution_run_id,
        pipeline_name=f"loa-{entity_type}",
        entity_type=entity_type
    )

    try:
        # Record processing start
        audit.record_processing_start(source_file=input_pattern)

        # Wrap pipeline execution in error context
        with ErrorContext(error_handler, operation_name="dataflow_execution"):
            options_dict = {
                'input_pattern': input_pattern,
                'output_table': output_table,
                'error_table': error_table,
                'run_id': execution_run_id,
                'project': project,
                'region': region,
                'runner': runner,
                'job_name': f"{job_name}-{entity_type}".replace("_", "-"),
                'temp_location': temp_location
            }

            options = PipelineOptions(flags=[], **options_dict)
            pipeline = LOAJCLPipeline(options, entity_type=entity_type)
            result = pipeline.run()

            # Collect statistics after pipeline completes
            stats = metrics_collector.get_statistics()
            logging.info(f"Pipeline metrics: {stats}")

            # Run health checks
            health_checker = HealthChecker(metrics_collector)
            health_results = health_checker.run_all_checks()
            is_healthy = health_checker.is_healthy()
            logging.info(f"Pipeline health status: {'HEALTHY' if is_healthy else 'UNHEALTHY'}")
            logging.info(f"Health check details: {health_results}")

            # Record audit end
            audit.increment_counts(
                valid=stats.get('validation_success', 0),
                errors=stats.get('validation_errors', 0)
            )
            audit.record_processing_end(success=True)

            return 0

    except Exception as e:
        # Record audit failure
        audit.record_processing_end(success=False)

        # Error handler logs and classifies errors automatically
        error_stats = error_handler.get_statistics()
        logging.error(f"Pipeline failed. Error statistics: {error_stats}", exc_info=True)

        # Check error severity to decide exit code
        critical_count = error_stats.get('severity_breakdown', {}).get('CRITICAL', 0)
        if critical_count > 0:
            return 1  # Critical error - fail immediately
        else:
            return 2  # Non-critical error - could retry


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="LOA JCL Migration Pipeline"
    )
    parser.add_argument(
        "--entity_type",
        default="applications",
        choices=["applications", "customers", "branches", "collateral"],
        help="Entity type being processed"
    )
    parser.add_argument(
        "--input_pattern",
        required=True,
        help="GCS wildcard pattern (e.g., gs://bucket/applications_*)"
    )
    parser.add_argument(
        "--output_table",
        required=True,
        help="BigQuery output table (project:dataset.table)"
    )
    parser.add_argument(
        "--error_table",
        required=True,
        help="BigQuery error table (project:dataset.table)"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID"
    )
    parser.add_argument(
        "--region",
        default="us-central1",
        help="GCP region"
    )
    parser.add_argument(
        "--runner",
        default="DirectRunner",
        choices=["DirectRunner", "DataflowRunner"],
        help="Beam runner"
    )
    parser.add_argument(
        "--temp_location",
        help="Temp location for Dataflow"
    )
    parser.add_argument(
        "--pubsub_topic",
        help="Pub/Sub topic for completion events"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run pipeline
    run_pipeline(
        input_pattern=args.input_pattern,
        output_table=args.output_table,
        error_table=args.error_table,
        project=args.project,
        entity_type=args.entity_type,
        region=args.region,
        runner=args.runner,
        temp_location=args.temp_location,
        pubsub_topic=args.pubsub_topic
    )

