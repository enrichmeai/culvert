"""
LOA Pipeline Module.

Apache Beam/Dataflow pipeline for LOA data migration.

Components:
- loa_pipeline: Main pipeline implementation
- dag_template: Airflow DAG factory (lazy loaded)
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
    AddAuditColumnsDoFn,
    run_loa_pipeline,
)

# Schema-driven validation from library
from gcp_pipeline_builder.pipelines.beam.transforms import SchemaValidateRecordDoFn

# dag_template imports are lazy - only import when needed
# from .dag_template import (
#     create_loa_dag,
#     create_loa_transformation_dag,
#     LOA_DEFAULT_ARGS,
# )
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


def get_dag_template():
    """Lazy import of DAG template to avoid airflow dependency at module level."""
    from .dag_template import (
        create_loa_dag,
        create_loa_transformation_dag,
        LOA_DEFAULT_ARGS,
    )
    return create_loa_dag, create_loa_transformation_dag, LOA_DEFAULT_ARGS


__all__ = [
    # Pipeline
    'LOA_ENTITY_CONFIG',
    'LOAPipelineOptions',
    'AddAuditColumnsDoFn',
    'run_loa_pipeline',
    # Schema-driven validation (from library)
    'SchemaValidateRecordDoFn',
    # DAG template (lazy)
    'get_dag_template',
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

