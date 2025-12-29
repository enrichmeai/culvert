"""
Base Pipeline Package

Core pipeline framework with configuration, options, and lifecycle management.

This package provides the foundational components for building robust
Apache Beam migration pipelines with integrated audit trail, error handling,
and metrics collection.

Exports:
    BasePipeline: Abstract base class for all GDW migration pipelines
    PipelineConfig: Configuration dataclass for pipelines
    GDWPipelineOptions: Command-line options for pipelines

Example:
    >>> from gdw_data_core.pipelines.base import BasePipeline, PipelineConfig
    >>>
    >>> class MyPipeline(BasePipeline):
    ...     def build(self, pipeline):
    ...         # Define pipeline logic here
    ...         pass
    >>>
    >>> config = PipelineConfig(
    ...     run_id='run_001',
    ...     pipeline_name='my_pipeline'
    ... )
    >>> pipeline = MyPipeline(config=config)
    >>> pipeline.run()
"""

from .config import PipelineConfig
from .options import GDWPipelineOptions
from .pipeline import BasePipeline
from . import lifecycle

__all__ = [
    'BasePipeline',
    'PipelineConfig',
    'GDWPipelineOptions',
    'lifecycle',
]

