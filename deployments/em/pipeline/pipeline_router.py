"""
Pipeline Router - Dynamic File Type Routing

Routes incoming files to appropriate pipeline based on file type and content.
Enables single DAG to handle multiple entity types (Applications, Customers, Branches, Collateral).

Usage: Identify file type → Select pipeline → Route for processing
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import re
from datetime import datetime
from gdw_data_core.orchestration.routing import (
    DAGRouter as BasePipelineRouter,
    PipelineConfig,
    FileType as CoreFileType,
    ProcessingMode as CoreProcessingMode
)

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported file types for routing."""
    APPLICATIONS = "applications"
    CUSTOMERS = "customers"
    BRANCHES = "branches"
    COLLATERAL = "collateral"
    UNKNOWN = "unknown"


class ProcessingMode(Enum):
    """Processing modes for routing."""
    DAILY = "daily"
    ONDEMAND = "ondemand"
    BATCH = "batch"
    RECOVERY = "recovery"


class PipelineRouter(BasePipelineRouter):
    """Routes files to appropriate pipeline."""

    def __init__(self):
        """Initialize router with known pipelines."""
        super().__init__()
        self._register_default_pipelines()

    def _register_default_pipelines(self):
        """Register default pipeline configurations."""

        # Applications Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.APPLICATIONS,
            dag_id="loa_applications_pipeline",
            entity_name="Applications",
            table_name="applications_raw",
            required_columns=[
                "application_id", "ssn", "loan_amount", "loan_type",
                "application_date", "branch_code"
            ],
            validation_rules={
                "ssn_format": r"^\d{3}-\d{2}-\d{4}$",
                "loan_amount_range": (10000, 1000000),
                "loan_types": ["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]
            }
        ))

        # Customers Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.CUSTOMERS,
            dag_id="loa_customers_pipeline",
            entity_name="Customers",
            table_name="customers_raw",
            required_columns=[
                "customer_id", "ssn", "customer_name", "account_number",
                "email", "phone", "credit_score", "branch_code"
            ],
            validation_rules={
                "ssn_format": r"^\d{3}-\d{2}-\d{4}$",
                "credit_score_range": (300, 850),
                "email_format": r"^[\w\.-]+@[\w\.-]+\.\w+$"
            }
        ))

        # Branches Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.BRANCHES,
            dag_id="loa_branches_pipeline",
            entity_name="Branches",
            table_name="branches_raw",
            required_columns=[
                "branch_code", "branch_name", "region", "state", "city",
                "manager_name", "employee_count"
            ],
            validation_rules={
                "state_code_length": 2,
                "employee_count_range": (0, 1000)
            }
        ))

        # Collateral Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.COLLATERAL,
            dag_id="loa_collateral_pipeline",
            entity_name="Collateral",
            table_name="collateral_raw",
            required_columns=[
                "collateral_id", "application_id", "collateral_type",
                "collateral_value", "appraisal_date"
            ],
            validation_rules={
                "collateral_types": ["PROPERTY", "VEHICLE", "SECURITIES"],
                "collateral_value_range": (10000, 500000)
            }
        ))

    def detect_file_type(self, file_path: str) -> FileType:
        """
        Detect file type from file path and name.
        """
        file_path_lower = file_path.lower()

        # Check for entity type keywords in path
        if "application" in file_path_lower or "app_" in file_path_lower:
            return FileType.APPLICATIONS
        elif "customer" in file_path_lower or "cust_" in file_path_lower:
            return FileType.CUSTOMERS
        elif "branch" in file_path_lower:
            return FileType.BRANCHES
        elif "collateral" in file_path_lower or "coll_" in file_path_lower:
            return FileType.COLLATERAL
        else:
            return FileType.UNKNOWN

    def detect_processing_mode(
        self,
        file_path: str,
        processing_timestamp: datetime = None
    ) -> ProcessingMode:
        """
        Detect processing mode (daily, on-demand, batch, recovery).
        """
        file_lower = file_path.lower()

        # Check for mode indicators
        if "recovery" in file_lower or "reprocess" in file_lower:
            return ProcessingMode.RECOVERY
        elif "batch" in file_lower:
            return ProcessingMode.BATCH
        elif "manual" in file_lower or "ondemand" in file_lower:
            return ProcessingMode.ONDEMAND
        else:
            # Default to daily
            return ProcessingMode.DAILY

    def route_file(self, file_path: str) -> Dict[str, Any]:
        """
        Route file to appropriate pipeline.
        """
        file_type = self.detect_file_type(file_path)
        mode = self.detect_processing_mode(file_path)
        config = self.get_pipeline_config(file_type)

        if not config:
            return {
                "file_path": file_path,
                "file_type": file_type.value if hasattr(file_type, "value") else str(file_type),
                "mode": mode.value if hasattr(mode, "value") else str(mode),
                "dag_id": None,
                "routable": False,
                "reason": f"Unknown file type: {file_type}"
            }

        return {
            "file_path": file_path,
            "file_type": file_type.value,
            "mode": mode.value,
            "dag_id": config.dag_id,
            "entity_name": config.entity_name,
            "table_name": config.table_name,
            "required_columns": config.required_columns,
            "validation_rules": config.validation_rules,
            "routable": True,
            "reason": "File routed successfully"
        }

    def get_all_pipelines(self) -> Dict[str, Any]:
        """Get all registered pipelines."""
        return {
            k.value if hasattr(k, "value") else str(k): {
                "entity_name": v.entity_name,
                "dag_id": v.dag_id,
                "table_name": getattr(v, "table_name", ""),
                "required_columns": v.required_columns
            }
            for k, v in self.pipelines.items()
        }

    def register_custom_pipeline(self, config: PipelineConfig) -> None:
        """Register a custom pipeline configuration."""
        self.register_pipeline(config)

    def validate_file_structure(
        self,
        file_type: Any,
        csv_columns: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that CSV columns match required columns.
        Handles both Core FileType and Local FileType.
        """
        # Convert columns to lowercase for case-insensitive comparison
        csv_columns_lower = [col.lower() for col in csv_columns]

        config = self.get_pipeline_config(file_type)
        if not config:
            return False, [f"Unknown file type: {file_type}"]

        required = [col.lower() for col in config.required_columns]
        missing = [col for col in required if col not in csv_columns_lower]

        return len(missing) == 0, missing


class DynamicPipelineSelector:
    """Selects pipeline based on multiple criteria."""

    def __init__(self):
        """Initialize selector."""
        self.router = PipelineRouter()

    def select_pipeline(
        self,
        file_path: str,
        csv_columns: Optional[List[str]] = None,
        file_size_mb: Optional[float] = None,
        record_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Select appropriate pipeline with validation.

        Args:
            file_path: File path
            csv_columns: CSV columns (optional, for validation)
            file_size_mb: File size in MB
            record_count: Number of records

        Returns:
            Selection decision with routing info
        """
        # Route file
        routing = self.router.route_file(file_path)

        if not routing["routable"]:
            return routing

        # Validate structure if columns provided
        file_type = FileType[routing["file_type"].upper()]
        if csv_columns:
            is_valid, errors = self.router.validate_file_structure(
                file_type,
                csv_columns
            )

            if not is_valid:
                routing["routable"] = False
                routing["validation_errors"] = errors
                return routing

        # Add processing hints
        routing["processing_hints"] = {
            "file_size_mb": file_size_mb,
            "record_count": record_count,
            "large_file": file_size_mb and file_size_mb > 100,
            "batch_recommended": record_count and record_count > 10000
        }

        return routing

