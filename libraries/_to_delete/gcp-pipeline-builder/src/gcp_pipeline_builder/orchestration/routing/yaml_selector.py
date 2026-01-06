"""
YAML-Based Pipeline Selector.

Provides YAML configuration-driven pipeline routing.
Complements DAGRouter with file-based configuration.

Usage:
    from gcp_pipeline_builder.orchestration.routing import YAMLPipelineSelector

    selector = YAMLPipelineSelector(config_path='routing_config.yaml')
    pipeline_id = selector.select_pipeline(metadata)

Config Format (YAML):
    default_pipeline: default_batch_pipeline
    routing_rules:
      - pipeline_id: applications_pipeline
        file_pattern: "*/applications_*"
        entity_type: applications
      - pipeline_id: customers_pipeline
        entity_type: customers
"""

import yaml
import fnmatch
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class YAMLPipelineSelector:
    """
    Intelligent routing engine that maps file patterns/metadata to pipeline identifiers.

    Loads routing rules from YAML configuration and matches incoming metadata
    against those rules to select the appropriate pipeline.

    Matching criteria (all must match if specified in rule):
    - file_pattern: fnmatch pattern against gcs_path
    - file_patterns: list of fnmatch patterns (any match)
    - system_id: exact match
    - entity_type: exact match
    - custom fields: exact match

    Args:
        config_path: Path to YAML configuration file (optional)
        config_dict: Configuration dictionary (optional, alternative to file)
        default_pipeline: Default pipeline if no rules match

    Example:
        >>> selector = YAMLPipelineSelector(config_path='config.yaml')
        >>> metadata = {'gcs_path': 'gs://bucket/applications_20260101.csv'}
        >>> pipeline = selector.select_pipeline(metadata)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        default_pipeline: str = "default_pipeline",
    ):
        self.config: Dict[str, Any] = {}
        self.default_pipeline = default_pipeline

        if config_dict:
            self.config = config_dict
        elif config_path:
            self.load_config(config_path)

    def load_config(self, config_path: str) -> None:
        """
        Load routing configuration from a YAML file.

        Args:
            config_path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r") as f:
            self.config = yaml.safe_load(f) or {}

        logger.info(f"Loaded routing config from {config_path}")

    def load_config_string(self, yaml_string: str) -> None:
        """
        Load routing configuration from a YAML string.

        Args:
            yaml_string: YAML configuration as string
        """
        self.config = yaml.safe_load(yaml_string) or {}

    def select_pipeline(self, metadata: Dict[str, Any]) -> str:
        """
        Select the appropriate pipeline based on metadata.

        Evaluates each rule in order and returns the first matching pipeline.
        If no rules match, returns the default pipeline.

        Args:
            metadata: Metadata dictionary (e.g., from PubSubPullSensor)
                Expected keys: gcs_path, system_id, entity_type, etc.

        Returns:
            The identifier of the selected pipeline
        """
        gcs_path = metadata.get("gcs_path", "")
        system_id = metadata.get("system_id")
        entity_type = metadata.get("entity_type")

        rules = self.config.get("routing_rules", [])

        for rule in rules:
            if self._matches_rule(rule, gcs_path, system_id, entity_type, metadata):
                pipeline_id = rule.get("pipeline_id")
                logger.debug(f"Matched rule for pipeline: {pipeline_id}")
                return pipeline_id

        # Return configured default or fallback
        default = self.config.get("default_pipeline") or self.config.get(
            "default_settings", {}
        ).get("default_pipeline", self.default_pipeline)

        logger.debug(f"No rules matched, using default: {default}")
        return default

    def _matches_rule(
        self,
        rule: Dict[str, Any],
        gcs_path: str,
        system_id: Optional[str],
        entity_type: Optional[str],
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Check if metadata matches a routing rule.

        All specified criteria in the rule must match.

        Args:
            rule: Routing rule dictionary
            gcs_path: GCS file path
            system_id: System identifier
            entity_type: Entity type
            metadata: Full metadata dictionary

        Returns:
            True if all criteria match, False otherwise
        """
        # Check file_pattern (single pattern)
        if "file_pattern" in rule and gcs_path:
            if not fnmatch.fnmatch(gcs_path, rule["file_pattern"]):
                return False

        # Check file_patterns (list of patterns - any match)
        if "file_patterns" in rule and gcs_path:
            patterns = rule["file_patterns"]
            if not any(fnmatch.fnmatch(gcs_path, p) for p in patterns):
                return False

        # Check system_id
        if "system_id" in rule and system_id is not None:
            if str(system_id) != str(rule["system_id"]):
                return False

        # Check entity_type
        if "entity_type" in rule and entity_type is not None:
            if entity_type != rule["entity_type"]:
                return False

        # Check any custom fields
        for key in rule:
            if key in ("pipeline_id", "file_pattern", "file_patterns",
                       "system_id", "entity_type", "target_table",
                       "error_table", "processing_mode", "validation",
                       "dataflow_template"):
                continue  # Skip known config keys
            if key in metadata:
                if metadata[key] != rule[key]:
                    return False

        return True

    def get_pipeline_config(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full configuration for a specific pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Pipeline configuration dict or None if not found
        """
        rules = self.config.get("routing_rules", [])
        for rule in rules:
            if rule.get("pipeline_id") == pipeline_id:
                return rule
        return None

    def get_all_pipeline_ids(self) -> List[str]:
        """
        Get list of all configured pipeline IDs.

        Returns:
            List of pipeline identifiers
        """
        rules = self.config.get("routing_rules", [])
        return [rule.get("pipeline_id") for rule in rules if rule.get("pipeline_id")]

    def get_default_settings(self) -> Dict[str, Any]:
        """
        Get default settings from configuration.

        Returns:
            Default settings dictionary
        """
        return self.config.get("default_settings", {})


__all__ = ["YAMLPipelineSelector"]

