"""
Generic FDP Transform DAG.

Runs dbt transformation for a specific FDP model. Triggered per-model by
data_ingestion_dag when that model's ODP dependencies are satisfied.

FDP dependency map (checked by data_ingestion_dag before triggering):
- event_transaction_excess: needs customers + accounts (JOIN)
- portfolio_account_excess: needs decision only (MAP)
- portfolio_account_facility: needs applications only (MAP)

Flow:
1. Verify the requested FDP model's dependencies are loaded
2. Run dbt staging models for the required entities
3. Run the specific dbt FDP model
4. Run dbt tests for that model
5. Update job control status

Tags: generic, fdp, dbt, transformation

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
