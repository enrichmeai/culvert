"""
Builders Package

Fluent builders for constructing test objects.

This package provides builder classes that use the fluent interface
for clean and readable test data construction.

Exports:
    RecordBuilder: Build test records
    CSVRecordBuilder: Build CSV records
    PipelineConfigBuilder: Build pipeline configurations
    BeamOptionsBuilder: Build Beam options
    TestPipelineBuilder: Build test pipelines

Example:
    >>> from gdw_data_core.testing.builders import RecordBuilder, PipelineConfigBuilder
    >>>
    >>> record = (RecordBuilder()
    ...     .with_field('id', '1')
    ...     .with_field('name', 'John')
    ...     .build())
    >>>
    >>> config = (PipelineConfigBuilder()
    ...     .with_run_id('test_001')
    ...     .with_pipeline_name('test_pipeline')
    ...     .build())
"""

from .record_builder import RecordBuilder, CSVRecordBuilder
from .config_builder import PipelineConfigBuilder, BeamOptionsBuilder
from .pipeline_builder import TestPipelineBuilder

__all__ = [
    'RecordBuilder',
    'CSVRecordBuilder',
    'PipelineConfigBuilder',
    'BeamOptionsBuilder',
    'TestPipelineBuilder',
]

