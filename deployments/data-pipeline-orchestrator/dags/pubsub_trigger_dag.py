"""
Generic Pub/Sub Trigger DAG.

Listens for .ok file arrival via Pub/Sub and triggers the ODP load pipeline.
This is the entry point for the Generic data processing flow.

Flow:
1. Pub/Sub sensor waits for file notification
2. Validates the .ok file and corresponding data file using HDRTRLParser
3. Triggers data_ingestion_dag for the appropriate entity

Tags: generic, trigger, pubsub

NOTE: This file is a thin wrapper around the config-driven DAG factory.
The actual DAG logic lives in dag_factory.py; system.yaml drives all
configuration (entities, infrastructure names, FDP dependencies, etc.).
"""

import pathlib
import sys

# Ensure the config package is importable from the dags/ directory
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config.config_loader import load_system_config
from dag_factory import create_dags

config = load_system_config(
    pathlib.Path(__file__).parent.parent / "config" / "system.yaml"
)
create_dags(config, globals())
