"""
Enhanced Base Pipeline for LOA Blueprint.
Supports streaming mode, Pub/Sub sources, and low-latency BigQuery writes.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, GoogleCloudOptions

from gdw_data_core.core.audit import AuditTrail
from gdw_data_core.core.error_handling import ErrorHandler
from gdw_data_core.core.monitoring import MetricsCollector
from gdw_data_core.core.utilities import generate_run_id

class BasePipeline(ABC):
    """
    Enhanced Base Pipeline with streaming support.
    """

    def __init__(
        self,
        options: Optional[PipelineOptions] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.options = options or PipelineOptions()
        self.config = config or {}

        # Enable streaming if specified in config or options
        self.is_streaming = self.config.get('streaming', False)
        standard_options = self.options.view_as(StandardOptions)
        if self.is_streaming:
            standard_options.streaming = True

        pipeline_name = self.config.get('pipeline_name', 'loa_pipeline')
        self.run_id = self.config.get('run_id', generate_run_id(pipeline_name))

        # Initialize core components
        self.audit_manager = AuditTrail(
            run_id=self.run_id,
            pipeline_name=pipeline_name,
            entity_type=self.config.get('entity_type', 'data')
        )
        self.error_handler = ErrorHandler(pipeline_name=pipeline_name, run_id=self.run_id)
        self.metrics_emitter = MetricsCollector(pipeline_name=pipeline_name, run_id=self.run_id)

    @abstractmethod
    def build(self, pipeline: beam.Pipeline):
        """Build pipeline steps."""
        pass

    def run(self):
        """Execute the pipeline."""
        with beam.Pipeline(options=self.options) as p:
            self.build(p)

    def read_source(self, pipeline: beam.Pipeline, source_config: Dict[str, Any]):
        """
        Helper to read from different sources (Pub/Sub or GCS).
        """
        if self.is_streaming or source_config.get('type') == 'pubsub':
            subscription = source_config.get('subscription')
            topic = source_config.get('topic')
            if subscription:
                return pipeline | "ReadFromPubSubSub" >> beam.io.ReadFromPubSub(subscription=subscription)
            else:
                return pipeline | "ReadFromPubSubTopic" >> beam.io.ReadFromPubSub(topic=topic)
        else:
            path = source_config.get('path')
            return pipeline | "ReadFromGCS" >> beam.io.ReadFromText(path)

    def write_to_bigquery(self, pcoll: beam.PCollection, table_spec: str, schema: Any):
        """
        Helper to write to BigQuery, using Storage Write API for streaming.
        """
        if self.is_streaming:
            return pcoll | "WriteToBQStreaming" >> beam.io.WriteToBigQuery(
                table_spec,
                schema=schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                method=beam.io.WriteToBigQuery.Method.STORAGE_WRITE_API
            )
        else:
            return pcoll | "WriteToBQBatch" >> beam.io.WriteToBigQuery(
                table_spec,
                schema=schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
            )
