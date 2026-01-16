"""
Windowing and Triggering Module

Reusable PTransforms for applying windowing and triggering strategies to PCollections.
"""

from typing import Optional, Union

import apache_beam as beam
from apache_beam.transforms import window
from apache_beam.transforms.trigger import (
    AfterWatermark,
    AfterProcessingTime,
    AfterCount,
    Repeatedly,
    OrFinally,
    AfterEach,
    AfterAll
)


class ApplyWindowing(beam.PTransform):
    """
    A reusable PTransform to apply windowing and triggering strategies.

    Support Fixed, Sliding, and Session windows with configurable lateness,
    accumulation mode, and triggers.

    Example:
        >>> pcoll | ApplyWindowing(
        ...     window_type='fixed',
        ...     size=60,
        ...     allowed_lateness=120,
        ...     accumulation_mode='accumulating'
        ... )
    """

    def __init__(
        self,
        window_type: str,
        size: Optional[int] = None,
        period: Optional[int] = None,
        gap: Optional[int] = None,
        allowed_lateness: int = 0,
        accumulation_mode: str = 'discarding',
        trigger: Optional[beam.transforms.trigger.TriggerFn] = None
    ):
        """
        Initialize ApplyWindowing.

        Args:
            window_type: 'fixed', 'sliding', or 'session'
            size: Window size in seconds (for fixed and sliding)
            period: Window period in seconds (for sliding)
            gap: Session gap in seconds (for session)
            allowed_lateness: Allowed lateness in seconds
            accumulation_mode: 'discarding' or 'accumulating'
            trigger: Optional Beam TriggerFn
        """
        super().__init__()
        self.window_type = window_type.lower()
        self.size = size
        self.period = period
        self.gap = gap
        self.allowed_lateness = allowed_lateness
        self.accumulation_mode = accumulation_mode.lower()
        self.trigger = trigger

    def expand(self, pcoll: beam.PCollection) -> beam.PCollection:
        if self.window_type == 'fixed':
            if self.size is None:
                raise ValueError("Size must be provided for fixed windows")
            window_fn = window.FixedWindows(self.size)
        elif self.window_type == 'sliding':
            if self.size is None or self.period is None:
                raise ValueError("Size and period must be provided for sliding windows")
            window_fn = window.SlidingWindows(self.size, self.period)
        elif self.window_type == 'session':
            if self.gap is None:
                raise ValueError("Gap must be provided for session windows")
            window_fn = window.Sessions(self.gap)
        else:
            raise ValueError(f"Unsupported window_type: {self.window_type}")

        acc_mode = (
            beam.transforms.trigger.AccumulationMode.ACCUMULATING
            if self.accumulation_mode == 'accumulating'
            else beam.transforms.trigger.AccumulationMode.DISCARDING
        )

        return pcoll | beam.WindowInto(
            window_fn,
            trigger=self.trigger,
            accumulation_mode=acc_mode,
            allowed_lateness=self.allowed_lateness
        )
