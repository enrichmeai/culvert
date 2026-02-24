"""
Generic Pipeline Runner.

Main entry point for Generic Dataflow pipeline.
"""

import argparse
import logging
from datetime import datetime

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition

from gcp_pipeline_core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)

from .options import EMPipelineOptions
from .transforms import ValidateFileDoFn, ParseAndValidateRecordDoFn
from ..config import (
    SYSTEM_ID,
    ODP_DATASET,
    CUSTOMERS_HEADERS,
    ACCOUNTS_HEADERS,
    DECISION_HEADERS,
)
from ..schema import ENTITY_SCHEMAS, get_schema

logger = logging.getLogger(__name__)


ENTITY_HEADERS = {
    'customers': CUSTOMERS_HEADERS,
    'accounts': ACCOUNTS_HEADERS,
    'decision': DECISION_HEADERS,
}


def run_pipeline(argv=None):
    """Run the Generic pipeline."""

    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)
    generic_options = pipeline_options.view_as(EMPipelineOptions)

    entity = generic_options.entity
    input_file = generic_options.input_file
    output_table = generic_options.output_table
    error_table = generic_options.error_table
    run_id = generic_options.run_id
    extract_date = generic_options.extract_date

    headers = ENTITY_HEADERS.get(entity)
    schema = ENTITY_SCHEMAS.get(entity)

    if not headers or not schema:
        raise ValueError(f"Unknown entity: {entity}")

    logger.info(f"Starting Generic pipeline for {entity}")
    logger.info(f"Input: {input_file}")
    logger.info(f"Output: {output_table}")
    logger.info(f"Run ID: {run_id}")

    with beam.Pipeline(options=pipeline_options) as p:
        # Read file content
        file_content = (
            p
            | 'ReadFile' >> beam.io.ReadFromText(input_file)
            | 'CombineLines' >> beam.CombineGlobally(lambda lines: '\n'.join(lines))
        )

        # Validate file structure
        validation_result = (
            file_content
            | 'ValidateFile' >> beam.ParDo(
                ValidateFileDoFn(entity)
            ).with_outputs('valid', 'invalid')
        )

        # Parse and validate records from valid files
        lines = (
            validation_result.valid
            | 'ExtractLines' >> beam.FlatMap(lambda x: x['lines'])
        )

        parsed_records = (
            lines
            | 'ParseAndValidate' >> beam.ParDo(
                ParseAndValidateRecordDoFn(
                    entity=entity,
                    headers=headers,
                    run_id=run_id,
                    source_file=input_file
                )
            ).with_outputs('valid', 'errors')
        )

        # Write valid records to BigQuery
        _ = (
            parsed_records.valid
            | 'WriteValid' >> WriteToBigQuery(
                output_table,
                schema=schema.to_bq_schema(),
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

        # Write error records to error table
        _ = (
            parsed_records.errors
            | 'WriteErrors' >> WriteToBigQuery(
                error_table,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

    logger.info(f"Generic pipeline completed for {entity}")


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run_pipeline()

