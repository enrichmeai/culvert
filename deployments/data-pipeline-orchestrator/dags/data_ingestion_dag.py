"""
Generic ODP Load DAG.

Loads Generic entity data (customers, accounts, decision, applications) to ODP (BigQuery).
Triggered by pubsub_trigger_dag after file validation.

Flow:
1. Create job control record
2. Run Dataflow pipeline to load data to ODP
3. Check which FDP models can now run based on granular dependencies
4. Trigger transformation_dag for each ready FDP model

FDP dependency map:
- event_transaction_excess: needs customers + accounts (JOIN)
- portfolio_account_excess: needs decision only (MAP)
- portfolio_account_facility: needs applications only (MAP)

Tags: generic, odp, dataflow

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
