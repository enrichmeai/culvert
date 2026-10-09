"""QualityCheckFailed — raised by ``@quality_check`` when a stage's output
falls below its required share of valid records (#3)."""

from __future__ import annotations

from typing import Sequence

from data_pipeline_core.job_control_api.types import FailureStage


class QualityCheckFailed(Exception):
    """The share of a stage's records that passed schema validation was
    below the stage's ``min_score``.

    A validation failure: ``failure_stage`` is ``FailureStage.VALIDATION``,
    which job control routes as not retryable (the same input fails again).

    Attributes:
        stage: The stage's name.
        valid: Records that passed validation.
        total: Records validated.
        min_score: The required share of valid records.
        sample: Up to five violations, as text, from the first invalid records.
    """

    failure_stage = FailureStage.VALIDATION

    def __init__(self, stage: str, valid: int, total: int, min_score: float,
                 sample: Sequence[str]) -> None:
        self.stage = stage
        self.valid = valid
        self.total = total
        self.min_score = min_score
        self.sample = tuple(sample)
        super().__init__(
            f"quality check failed for stage '{stage}': {valid} of {total} records valid "
            f"({valid / total:.4f}), below min_score={min_score}"
            + (f"; first violations: {'; '.join(self.sample)}" if self.sample else ""))
