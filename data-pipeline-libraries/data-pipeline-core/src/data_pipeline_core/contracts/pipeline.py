"""Pipeline and PipelineStage — composition primitives.

A `Pipeline` is a graph of `PipelineStage` nodes. The pipeline does not
know what runtime it will execute on; the runtime (a Composer DAG, a
Dataflow Flex template, a local in-process runner, a future AWS Step
Functions execution) is responsible for picking it up and scheduling
its stages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:
    from data_pipeline_core.contracts.runtime import RuntimeContext


@runtime_checkable
class PipelineStage(Protocol):
    """A named, dependency-aware unit of work inside a pipeline.

    `inputs` and `outputs` reference other stage names by string. The
    framework uses these to compute execution order and to validate
    that every input has a producer.
    """

    name: str
    inputs: Sequence[str]
    outputs: Sequence[str]

    def execute(self, context: "RuntimeContext") -> None: ...


@runtime_checkable
class Pipeline(Protocol):
    """Composition of stages, scheduler-agnostic.

    `validate()` checks the graph (no orphan inputs, no cycles, every
    stage's inputs are produced by an earlier stage). It raises if
    the pipeline cannot run; it does not return a bool.
    """

    name: str
    stages: Sequence[PipelineStage]

    def validate(self) -> None: ...
