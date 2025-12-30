import unittest
from unittest.mock import MagicMock
import os
import yaml
from blueprint.components.loa_pipelines.yaml_router import PipelineSelector

class TestPipelineSelector(unittest.TestCase):
    def setUp(self):
        self.config_data = {
            'default_pipeline': 'default_pipeline',
            'routing_rules': [
                {
                    'pipeline_id': 'type_a_pipeline',
                    'file_pattern': '*/TYPE_A_*',
                    'entity_type': 'applications'
                },
                {
                    'pipeline_id': 'realtime_pipeline',
                    'entity_type': 'realtime_event'
                }
            ]
        }
        self.config_path = 'test_routing_config.yaml'
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        self.selector = PipelineSelector(self.config_path)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_select_by_pattern(self):
        metadata = {
            'gcs_path': 'gs://bucket/incoming/TYPE_A_data.csv',
            'entity_type': 'applications'
        }
        pipeline_id = self.selector.select_pipeline(metadata)
        self.assertEqual(pipeline_id, 'type_a_pipeline')

    def test_select_by_entity_type(self):
        metadata = {
            'entity_type': 'realtime_event'
        }
        pipeline_id = self.selector.select_pipeline(metadata)
        self.assertEqual(pipeline_id, 'realtime_pipeline')

    def test_default_fallback(self):
        metadata = {
            'entity_type': 'unknown'
        }
        pipeline_id = self.selector.select_pipeline(metadata)
        self.assertEqual(pipeline_id, 'default_pipeline')

if __name__ == '__main__':
    unittest.main()
