"""
Generic pipeline DAG entrypoint.

All DAG logic lives in gcp-pipeline-orchestration. This file is the only
entrypoint needed — Airflow discovers all four DAGs from here:

  - generic_pubsub_trigger_dag
  - generic_ingestion_dag
  - generic_transformation_dag
  - generic_pipeline_status_dag

To adopt this pattern for a new system, copy this file, point config_path
at your deployment's system.yaml, and Airflow generates the full pipeline.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.config_loader import load_system_config
from gcp_pipeline_orchestration.factories.dag_factory import create_dags

config = load_system_config()
create_dags(config, globals())
