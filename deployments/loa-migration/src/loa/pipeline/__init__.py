"""
LOA Pipeline Module.

Apache Beam/Dataflow pipeline for LOA data migration.

Components:
- loa_pipeline: Main pipeline implementation
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
from gcp_pipeline_beam.pipelines.beam.transforms import SchemaValidateRecordDoFn

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
    'AddAuditColumnsDoFn',
    'run_loa_pipeline',
    # Schema-driven validation (from library)
    'SchemaValidateRecordDoFn',
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
