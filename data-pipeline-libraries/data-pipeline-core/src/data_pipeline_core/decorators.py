"""Stage 3 decorators — declarative pipeline composition.

Lightweight markers that register classes/functions with the auto-config
registry. The framework then walks the registry to assemble a pipeline.

These are intentionally thin: they don't impose any base class or
metaclass on the decorated target; they just tag it with metadata
attributes that the registry reads.

Sprint-4 deliverable.
"""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from data_pipeline_core.autoconfig import register_adapter

T = TypeVar("T")


def pipeline(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Pipeline impl. Also registers it with the
    auto-config registry under ``pipeline``.

    .. code-block:: python

        @pipeline(name="customer-ingest")
        class CustomerIngest:
            def name(self): return "customer-ingest"
            def stages(self): return [...]
            def validate(self): ...
    """
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_pipeline_name__", name or cls.__name__)
        register_adapter("pipeline")(cls)
        return cls
    return decorator


def stage(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a PipelineStage impl. Registers under ``runtime``
    (PipelineStages are runtime fragments, not adapters)."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_stage_name__", name or cls.__name__)
        return cls
    return decorator


def source(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Source impl. Registers under ``source``."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_source_name__", name or cls.__name__)
        register_adapter("source")(cls)
        return cls
    return decorator


def sink(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Sink impl. Registers under ``sink``."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_sink_name__", name or cls.__name__)
        register_adapter("sink")(cls)
        return cls
    return decorator


def transform(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Transform impl. Registers under ``transform``."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_transform_name__", name or cls.__name__)
        register_adapter("transform")(cls)
        return cls
    return decorator


__all__ = ["pipeline", "stage", "source", "sink", "transform"]
