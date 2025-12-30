"""
Routing configuration engine for LOA Blueprint.
"""

import yaml
import fnmatch
from typing import Dict, Any, Optional, List

class PipelineSelector:
    """
    Intelligent routing engine that maps file patterns/metadata to pipeline identifiers.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config = {}
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: str):
        """Loads routing configuration from a YAML file."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def select_pipeline(self, metadata: Dict[str, Any]) -> str:
        """
        Selects the appropriate pipeline based on metadata.

        Args:
            metadata: Metadata dictionary (e.g., from LOAPubSubPullSensor)

        Returns:
            The identifier of the pipeline to run.
        """
        gcs_path = metadata.get('gcs_path', '')
        system_id = metadata.get('system_id')
        entity_type = metadata.get('entity_type')

        # Try to match based on rules in config
        rules = self.config.get('routing_rules', [])
        for rule in rules:
            match = True

            if 'file_pattern' in rule and gcs_path:
                if not fnmatch.fnmatch(gcs_path, rule['file_pattern']):
                    match = False

            if 'system_id' in rule and system_id:
                if str(system_id) != str(rule['system_id']):
                    match = False

            if 'entity_type' in rule and entity_type:
                if entity_type != rule['entity_type']:
                    match = False

            if match:
                return rule['pipeline_id']

        # Default fallback
        return self.config.get('default_pipeline', 'default_loa_pipeline')
