"""
Consumable Data Product (CDP) Segmentation Pipeline

This reference implementation demonstrates how to:
1. Read multiple BigQuery tables (FDP tables)
2. Perform processing/segmentation logic
3. Write segmented data to GCS for downstream consumption
"""

import logging
import argparse
from typing import Dict, Any, List

import apache_beam as beam
from gcp_pipeline_beam.pipelines.beam import BeamPipelineBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def segment_by_region(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example transformation logic for CDP processing.
    Here we add a segmentation tag and normalize field names.
    """
    # Simple segmentation logic: add segment tag based on region
    region = record.get('region', 'UNKNOWN')
    record['cdp_segment'] = f"SEGMENT_{region}"
    
    # Normalize data for downstream systems
    if 'customer_id' in record:
        record['cid'] = record.pop('customer_id')
        
    return record


def run_cdp_pipeline(
    project_id: str,
    fdp_dataset: str,
    fdp_tables: List[str],
    output_bucket: str,
    output_prefix: str,
    segment_size: int,
    run_id: str
):
    """
    Constructs and runs the CDP pipeline for multiple tables.
    """
    logger.info(f"Starting CDP pipeline for tables: {fdp_tables}")
    
    builder = BeamPipelineBuilder(
        pipeline_name=f"cdp_multi_export",
        run_id=run_id
    )
    
    # Prepare sources for multiple tables
    sources = [{'dataset': fdp_dataset, 'table': table} for table in fdp_tables]
    
    # Using the fluent API to build the CDP flow for multiple sources
    result = (
        builder
        .read_from_bigquery(sources=sources)
        .enrich_metadata()
        .transform(segment_by_region)
        .write_segmented_to_gcs(
            bucket=output_bucket,
            prefix=f"{output_prefix}/multi_table/",
            segment_size=segment_size
        )
    )
    
    # Handle error output - production best practice
    if builder.error_pcoll:
        logger.info("Adding error handling for failed exports")
        # Route errors to a Dead Letter Queue (DLQ) in GCS
        builder.error_pcoll | 'WriteErrorsToGCS' >> beam.io.WriteToText(
            f"gs://{output_bucket}/{output_prefix}/errors/{run_id}/error_log",
            file_name_suffix=".jsonl"
        )
    
    # Run the pipeline
    final_result = result.run()
    
    logger.info("CDP Pipeline with multiple sources submitted to Dataflow")
    return final_result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run CDP Segmentation Pipeline')
    parser.add_argument('--project', required=True, help='GCP Project ID')
    parser.add_argument('--dataset', required=True, help='Source FDP Dataset')
    parser.add_argument('--tables', required=True, help='Comma-separated list of source FDP Tables')
    parser.add_argument('--bucket', required=True, help='Target GCS Bucket')
    parser.add_argument('--prefix', default='cdp_segments', help='GCS Path Prefix')
    parser.add_argument('--segment_size', type=int, default=10000, help='Records per segment')
    parser.add_argument('--run_id', default='manual_run_001', help='Unique Run Identifier')

    args = parser.parse_args()
    
    table_list = [t.strip() for t in args.tables.split(',')]

    run_cdp_pipeline(
        project_id=args.project,
        fdp_dataset=args.dataset,
        fdp_tables=table_list,
        output_bucket=args.bucket,
        output_prefix=args.prefix,
        segment_size=args.segment_size,
        run_id=args.run_id
    )
