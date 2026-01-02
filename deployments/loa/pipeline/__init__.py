"""
LOA Pipeline Module.

Apache Beam/Dataflow pipeline for LOA data migration.

Components:
- loa_pipeline: Main pipeline implementation
- dag_template: Airflow DAG factory
- pipeline_router: File routing logic
- transforms: Beam DoFn classes
- options: Pipeline command-line options
- runner: Pipeline entry point

Key Difference from EM:
- Single entity (applications) - no dependency wait
- Immediate FDP trigger after ODP load
- SPLIT transformation (1 ODP → 2 FDP tables)
"""

from .loa_pipeline import (
    LOA_ENTITY_CONFIG,
    LOAPipelineOptions,
    ValidateLOARecordDoFn,
    AddAuditColumnsDoFn,
    run_loa_pipeline,
)
from .dag_template import (
    create_loa_dag,
    create_loa_transformation_dag,
    LOA_DEFAULT_ARGS,
)
from .pipeline_router import (
    PipelineRouter,
    FileType,
    ProcessingMode,
)
from .transforms import (
    ValidateFileDoFn,
    ParseAndValidateRecordDoFn,
    AddExtractDateDoFn,
    FilterByEventTypeDoFn,
    FilterByPortfolioDoFn,
    CreateEventKeyDoFn,
    CreatePortfolioKeyDoFn,
)
from .options import LOAPipelineOptions as Options
from .runner import run, main

__all__ = [
    # Pipeline
    'LOA_ENTITY_CONFIG',
    'LOAPipelineOptions',
    'ValidateLOARecordDoFn',
    'AddAuditColumnsDoFn',
    'run_loa_pipeline',
    # DAG template
    'create_loa_dag',
    'create_loa_transformation_dag',
    'LOA_DEFAULT_ARGS',
    # Router
    'PipelineRouter',
    'FileType',
    'ProcessingMode',
    # Transforms
    'ValidateFileDoFn',
    'ParseAndValidateRecordDoFn',
    'AddExtractDateDoFn',
    'FilterByEventTypeDoFn',
    'FilterByPortfolioDoFn',
    'CreateEventKeyDoFn',
    'CreatePortfolioKeyDoFn',
    # Options
    'Options',
    # Runner
    'run',
    'main',
]

