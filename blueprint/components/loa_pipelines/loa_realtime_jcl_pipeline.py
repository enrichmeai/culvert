"""
Real-time JCL streaming pipeline demonstration.
"""

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from loa_blueprint.pipelines.base import BasePipeline
from typing import Dict, Any

class LOARealtimeJCLPipeline(BasePipeline):
    """
    Demonstrates a streaming Dataflow job using the LOA Blueprint BasePipeline.
    """

    def build(self, pipeline: beam.Pipeline):
        # 1. Read from Pub/Sub (streaming)
        source_config = {
            'type': 'pubsub',
            'subscription': self.config.get('input_subscription')
        }

        raw_data = self.read_source(pipeline, source_config)

        # 2. Parse and Validate
        def parse_and_validate(message):
            # Simulation of parsing and validation logic
            try:
                import json
                data = json.loads(message.decode('utf-8'))
                # Add metadata
                data['run_id'] = self.run_id
                data['processed_at'] = 'now' # Placeholder
                return [data]
            except Exception as e:
                return []

        validated_records = (
            raw_data
            | "ParseAndValidate" >> beam.FlatMap(parse_and_validate)
        )

        # 3. Write to BigQuery (using Storage Write API for low latency)
        table_spec = self.config.get('output_table')
        schema = {
            'fields': [
                {'name': 'id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'amount', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                {'name': 'run_id', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'processed_at', 'type': 'STRING', 'mode': 'REQUIRED'}
            ]
        }

        self.write_to_bigquery(validated_records, table_spec, schema)

if __name__ == '__main__':
    # Usage example
    options = PipelineOptions([
        '--streaming',
        '--runner=DirectRunner',
        '--project=blueprint-project'
    ])

    config = {
        'streaming': True,
        'pipeline_name': 'generic_realtime_pipeline',
        'input_subscription': 'projects/blueprint-project/subscriptions/event-stream-sub',
        'output_table': 'blueprint-project:processed_data.streaming_table'
    }

    pipeline = LOARealtimeJCLPipeline(options, config)
    pipeline.run()
