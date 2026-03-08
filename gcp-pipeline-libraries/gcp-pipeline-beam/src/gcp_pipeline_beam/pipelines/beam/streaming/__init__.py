"""
Streaming module for gcp-pipeline-beam.

Provides transforms for streaming pipelines including:
- CDC (Change Data Capture) parsing
- Windowing strategies
- Streaming sinks
"""

from gcp_pipeline_beam.pipelines.beam.streaming.cdc import (
    ParseCDCEventDoFn,
    ParseDebeziumCDCDoFn,
    ParseSimpleCDCDoFn,
    CDCOperation,
)
from gcp_pipeline_beam.pipelines.beam.streaming.windows import (
    StreamingWindowStrategies,
    apply_tumbling_window,
    apply_sliding_window,
    apply_session_window,
    apply_micro_batch_window,
)
from gcp_pipeline_beam.pipelines.beam.streaming.transforms import (
    AddStreamingAuditDoFn,
    TransformToODPDoFn,
    TransformToFDPDoFn,
    FilterByOperationDoFn,
)

__all__ = [
    # CDC Parsing
    "ParseCDCEventDoFn",
    "ParseDebeziumCDCDoFn",
    "ParseSimpleCDCDoFn",
    "CDCOperation",
    # Windowing
    "StreamingWindowStrategies",
    "apply_tumbling_window",
    "apply_sliding_window",
    "apply_session_window",
    "apply_micro_batch_window",
    # Transforms
    "AddStreamingAuditDoFn",
    "TransformToODPDoFn",
    "TransformToFDPDoFn",
    "FilterByOperationDoFn",
]

