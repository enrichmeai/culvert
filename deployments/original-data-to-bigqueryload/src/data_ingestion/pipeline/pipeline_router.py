"""
Generic Pipeline Router - Dynamic File Type Routing

Routes incoming files to appropriate pipeline based on file type and content.
Handles Generic entity types: Customers, Accounts, Decision.

Generic Flow: 3 entities → ODP tables → Transformation → 2 FDP tables

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

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported entity file types for routing."""
    CUSTOMERS = "customers"
    ACCOUNTS = "accounts"
    DECISION = "decision"
    APPLICATIONS = "applications"
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
        """Initialize router with registered pipelines."""
        super().__init__()
        self._register_default_pipelines()

    def _register_default_pipelines(self):
        """Register pipeline configurations."""

        # Generic: Customers Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.CUSTOMERS,
            dag_id="data_ingestion_dag",
            entity_name="Customers",
            table_name="customers",
            required_columns=[
                "customer_id", "ssn", "customer_name", "date_of_birth",
                "email", "phone", "address", "city", "state", "zip_code"
            ],
            validation_rules={
                "ssn_format": r"^\d{3}-\d{2}-\d{4}$",
                "email_format": r"^[\w\.-]+@[\w\.-]+\.\w+$",
                "state_code_length": 2
            }
        ))

        # Generic: Accounts Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.ACCOUNTS,
            dag_id="data_ingestion_dag",
            entity_name="Accounts",
            table_name="accounts",
            required_columns=[
                "account_id", "customer_id", "account_type", "account_status",
                "balance", "open_date", "branch_code"
            ],
            validation_rules={
                "account_types": ["CHECKING", "SAVINGS", "MONEY_MARKET", "CD"],
                "balance_range": (0, 10000000),
                "account_statuses": ["ACTIVE", "CLOSED", "DORMANT", "FROZEN"]
            }
        ))

        # Generic: Decision Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.DECISION,
            dag_id="data_ingestion_dag",
            entity_name="Decision",
            table_name="decision",
            required_columns=[
                "decision_id", "customer_id", "account_id", "decision_type",
                "decision_date", "decision_score", "decision_outcome"
            ],
            validation_rules={
                "decision_types": ["CREDIT", "RISK", "FRAUD", "COMPLIANCE"],
                "decision_score_range": (0, 1000),
                "decision_outcomes": ["APPROVED", "DENIED", "PENDING", "REVIEW"]
            }
        ))

        # Generic: Applications Pipeline
        self.register_pipeline(PipelineConfig(
            file_type=FileType.APPLICATIONS,
            dag_id="data_ingestion_dag",
            entity_name="Applications",
            table_name="applications",
            required_columns=[
                "application_id", "customer_id", "application_type",
                "application_status", "submission_date", "amount_requested"
            ],
            validation_rules={
                "application_types": ["LOAN", "CREDIT_CARD", "MORTGAGE"],
                "amount_range": (0, 5000000),
                "application_statuses": ["SUBMITTED", "IN_REVIEW", "APPROVED", "DECLINED"]
            }
        ))

    def detect_file_type(self, file_path: str) -> FileType:
        """
        Detect file type from file path and name.
        """
        file_path_lower = file_path.lower()

        # Check for entity type keywords in path
        if "customer" in file_path_lower or "cust_" in file_path_lower:
            return FileType.CUSTOMERS
        elif "account" in file_path_lower or "acct_" in file_path_lower:
            return FileType.ACCOUNTS
        elif "decision" in file_path_lower or "dec_" in file_path_lower:
            return FileType.DECISION
        elif "application" in file_path_lower or "app_" in file_path_lower:
            return FileType.APPLICATIONS
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
        file_type = FileType.__members__.get(routing["file_type"].upper(), FileType.UNKNOWN)
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

