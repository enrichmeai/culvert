"""
Dataflow Streaming Health Sensor Module
"""

import logging
from typing import Any, Optional
from datetime import timedelta

try:
    from airflow.sensors.base import BaseSensorOperator
    from airflow.utils.context import Context
    from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    BaseSensorOperator = object

logger = logging.getLogger(__name__)

class DataflowStreamingSensor(BaseSensorOperator):
    """
    Checks the Audit Trail and fails if the heartbeat is missing.

    Args:
        audit_table: BigQuery audit trail table (project.dataset.table)
        pipeline_name: Name of the pipeline to monitor
        heartbeat_interval_minutes: Threshold for missing heartbeat
        gcp_conn_id: GCP connection ID
    """

    template_fields = ("audit_table", "pipeline_name")

    def __init__(
        self,
        audit_table: str,
        pipeline_name: str,
        heartbeat_interval_minutes: int = 15,
        gcp_conn_id: str = "google_cloud_default",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.audit_table = audit_table
        self.pipeline_name = pipeline_name
        self.heartbeat_interval_minutes = heartbeat_interval_minutes
        self.gcp_conn_id = gcp_conn_id

    def poke(self, context: 'Context') -> bool:
        if not AIRFLOW_AVAILABLE:
            raise ImportError("Airflow is not available")

        hook = BigQueryHook(gcp_conn_id=self.gcp_conn_id)
        
        query = f"""
            SELECT 
                MAX(last_seen) as last_heartbeat
            FROM `{self.audit_table}`
            WHERE pipeline_name = '{self.pipeline_name}'
              AND status = 'RUNNING'
        """
        
        records = hook.get_first(query)
        
        if not records or records[0] is None:
            logger.warning(f"No active pipeline found for {self.pipeline_name}")
            return False
            
        last_heartbeat = records[0]
        # Compare last_heartbeat with current time
        # This is simplified; in production we'd use BQ's CURRENT_TIMESTAMP or handle timezones
        
        query_staleness = f"""
            SELECT 
                TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(last_seen), MINUTE) as staleness_mins
            FROM `{self.audit_table}`
            WHERE pipeline_name = '{self.pipeline_name}'
              AND status = 'RUNNING'
        """
        staleness_records = hook.get_first(query_staleness)
        
        if staleness_records and staleness_records[0] is not None:
            staleness = staleness_records[0]
            if staleness > self.heartbeat_interval_minutes:
                raise ValueError(
                    f"Pipeline {self.pipeline_name} heartbeat is stale by {staleness} minutes "
                    f"(threshold: {self.heartbeat_interval_minutes})"
                )
            logger.info(f"Pipeline {self.pipeline_name} is healthy (staleness: {staleness} mins)")
            return True
            
        return False
