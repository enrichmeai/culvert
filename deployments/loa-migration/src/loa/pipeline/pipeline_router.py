"""
LOA Pipeline Router - Dynamic File Type Routing

Routes incoming files to appropriate pipeline based on file type and content.
LOA has a single entity (Applications) but router pattern provides extensibility.

Usage: Identify file type → Select pipeline → Route for processing
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import re
from datetime import datetime

from gcp_pipeline_orchestration.routing import (
    DAGRouter as BasePipelineRouter,
    PipelineConfig,
    FileType as CoreFileType,
    ProcessingMode as CoreProcessingMode
)

from ..config import (
    SYSTEM_ID,
    APPLICATIONS_HEADERS,
    ALLOWED_APPLICATION_STATUSES,
    ALLOWED_APPLICATION_TYPES,
)

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported file types for LOA routing."""
    APPLICATIONS = "applications"
    UNKNOWN = "unknown"


class ProcessingMode(Enum):
    """Processing modes for routing."""
    DAILY = "daily"
    ONDEMAND = "ondemand"
    BATCH = "batch"
    RECOVERY = "recovery"


class PipelineRouter(BasePipelineRouter):
    """
    Routes LOA files to appropriate pipeline.

    LOA has single entity (Applications), but router pattern
    provides extensibility for future entities.
    """

    def __init__(self):
        """Initialize router with LOA pipelines."""
        super().__init__()
        self._register_loa_pipelines()

    def _register_loa_pipelines(self):
        """Register LOA pipeline configurations."""

        # Applications Pipeline (the only LOA entity)
        self.register_pipeline(PipelineConfig(
            file_type=FileType.APPLICATIONS,
            dag_id="loa_applications_pipeline",
            entity_name="Applications",
            table_name="applications",
            required_columns=[
                "application_id",
                "customer_id",
                "application_date",
                "application_type",
                "application_status",
                "loan_amount",
            ],
            validation_rules={
                "application_statuses": ALLOWED_APPLICATION_STATUSES,
                "application_types": ALLOWED_APPLICATION_TYPES,
            }
        ))

    def detect_file_type(self, filename: str) -> FileType:
        """
        Detect file type from filename.

        Args:
            filename: Name of the file

        Returns:
            FileType enum value
        """
        filename_lower = filename.lower()

        # LOA file patterns
        if "application" in filename_lower or "loa_" in filename_lower:
            return FileType.APPLICATIONS

        return FileType.UNKNOWN

    def get_pipeline_config(self, file_type: FileType) -> Optional[PipelineConfig]:
        """
        Get pipeline configuration for file type.

        Args:
            file_type: FileType enum value

        Returns:
            PipelineConfig if found, None otherwise
        """
        return self._pipelines.get(file_type)

    def validate_file_structure(
        self,
        file_type: FileType,
        headers: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate file structure against expected schema.

        Args:
            file_type: FileType enum value
            headers: List of column headers from file

        Returns:
            Tuple of (is_valid, error_messages)
        """
        config = self.get_pipeline_config(file_type)
        if not config:
            return False, [f"Unknown file type: {file_type}"]

        errors = []
        missing_columns = []

        for required_col in config.required_columns:
            if required_col not in headers:
                missing_columns.append(required_col)

        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")

        return len(errors) == 0, errors

    def route_file(
        self,
        filename: str,
        headers: List[str],
        mode: ProcessingMode = ProcessingMode.DAILY
    ) -> Dict[str, Any]:
        """
        Route file to appropriate pipeline.

        Args:
            filename: Name of the file
            headers: Column headers from file
            mode: Processing mode

        Returns:
            Dict with routing information
        """
        file_type = self.detect_file_type(filename)

        if file_type == FileType.UNKNOWN:
            return {
                "status": "error",
                "message": f"Could not detect file type for: {filename}",
                "file_type": None,
                "dag_id": None,
            }

        is_valid, errors = self.validate_file_structure(file_type, headers)
        config = self.get_pipeline_config(file_type)

        if not is_valid:
            return {
                "status": "validation_failed",
                "message": f"File validation failed: {errors}",
                "file_type": file_type.value,
                "dag_id": config.dag_id if config else None,
                "errors": errors,
            }

        return {
            "status": "ready",
            "message": f"File routed to {config.dag_id}",
            "file_type": file_type.value,
            "dag_id": config.dag_id,
            "entity_name": config.entity_name,
            "table_name": config.table_name,
            "mode": mode.value,
        }

    def get_all_entity_names(self) -> List[str]:
        """Get all registered entity names."""
        return [config.entity_name for config in self._pipelines.values()]

    def get_all_dag_ids(self) -> List[str]:
        """Get all registered DAG IDs."""
        return [config.dag_id for config in self._pipelines.values()]

