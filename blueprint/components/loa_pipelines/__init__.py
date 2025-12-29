"""
LOA Pipelines Package
"""

__version__ = "1.0.0"
__author__ = "Data Engineering Team"

# Lazy imports to avoid heavy dependencies (like apache-beam) during routing/orchestration
def get_pipeline_class():
    from .loa_jcl_template import LOAJCLPipeline
    return LOAJCLPipeline

from .pipeline_router import (
    PipelineRouter,
    FileType,
    ProcessingMode,
    DynamicPipelineSelector
)

__all__ = [
    "PipelineRouter",
    "FileType",
    "ProcessingMode",
    "DynamicPipelineSelector",
    "get_pipeline_class",
]

