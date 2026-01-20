"""
Pipeline Router

Dynamic file type routing and configuration resolution for pipelines.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple

from .config import PipelineConfig, FileType, ProcessingMode

logger = logging.getLogger(__name__)


class DAGRouter:
    """
    Router for dynamic file type routing and configuration resolution.

    Handles:
    - Dynamic file type detection
    - Pipeline configuration registration
    - Configuration validation
    - File structure validation

    Usage:
        ```python
        router = DAGRouter()

        # Register pipeline configurations
        config = PipelineConfig(
            file_type=FileType.DATA,
            dag_id='daily_migration',
            entity_name='applications',
            table_name='stg_applications',
            required_columns=['app_id', 'status']
        )
        router.register_pipeline(config)

        # Get configuration for file type
        config = router.get_pipeline_config(FileType.DATA)

        # Validate file structure
        is_valid, missing = router.validate_file_structure(
            FileType.DATA,
            ['app_id', 'status', 'extra_col']
        )
        ```
    """

    def __init__(self):
        """Initialize router."""
        self.pipelines: Dict[Any, PipelineConfig] = {}
        self._file_type_patterns: Dict[str, Any] = {}

    def detect_file_type(self, file_path: str) -> Any:
        """
        Detect file type from path/name using registered patterns.

        Args:
            file_path: File path or name

        Returns:
            Detected FileType or UNKNOWN
        """
        if not file_path:
            return FileType.UNKNOWN

        # Check registered patterns
        for pattern, file_type in self._file_type_patterns.items():
            if re.search(pattern, file_path, re.IGNORECASE):
                return file_type

        # Try to infer from extension
        if file_path.endswith('.log'):
            return FileType.LOGS
        elif file_path.endswith('.json') or file_path.endswith('.xml'):
            return FileType.METADATA
        elif file_path.endswith('.csv') or file_path.endswith('.txt'):
            return FileType.DATA

        return FileType.UNKNOWN

    def register_file_type_pattern(self, pattern: str, file_type: Any) -> None:
        """
        Register a regex pattern for file type detection.

        Args:
            pattern: Regex pattern
            file_type: Associated file type
        """
        self._file_type_patterns[pattern] = file_type
        logger.info(f"Registered file type pattern: {pattern} -> {file_type}")

    def register_pipeline(self, config: PipelineConfig) -> None:
        """
        Register a pipeline configuration.

        Args:
            config: PipelineConfig instance

        Raises:
            ValueError: If config is invalid
        """
        config.validate()
        self.pipelines[config.file_type] = config
        logger.info(f"Registered pipeline for {config.file_type}")

    def get_pipeline_config(self, file_type: Any) -> Optional[PipelineConfig]:
        """
        Get pipeline configuration for file type.

        Args:
            file_type: File type

        Returns:
            PipelineConfig if found, None otherwise
        """
        return self.pipelines.get(file_type)

    def validate_file_structure(
        self,
        file_type: Any,
        csv_columns: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that CSV columns match required columns.

        Args:
            file_type: File type
            csv_columns: Column names from CSV

        Returns:
            Tuple of (is_valid, missing_columns)
        """
        config = self.get_pipeline_config(file_type)
        if not config:
            return False, [f"No pipeline registered for {file_type}"]

        missing = [col for col in config.required_columns if col not in csv_columns]
        is_valid = len(missing) == 0

        return is_valid, missing

    def get_registered_file_types(self) -> List[Any]:
        """
        Get list of registered file types.

        Returns:
            List of file types
        """
        return list(self.pipelines.keys())

    def unregister_pipeline(self, file_type: Any) -> None:
        """
        Unregister a pipeline configuration.

        Args:
            file_type: File type to unregister
        """
        if file_type in self.pipelines:
            del self.pipelines[file_type]
            logger.info(f"Unregistered pipeline for {file_type}")


__all__ = ['DAGRouter']

