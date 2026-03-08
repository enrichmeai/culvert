"""
Streaming Window Strategies.

Pre-built windowing configurations for CDC streaming pipelines.
Covers the standard patterns used in this reference implementation:
- Fixed windows with early/late firing (ODP latency control)
- Session windows (per-entity activity grouping)
"""

from apache_beam.transforms.window import FixedWindows, SlidingWindows, Sessions
from apache_beam.transforms.trigger import (
    AfterWatermark,
    AfterProcessingTime,
    AccumulationMode,
)


class StreamingWindowStrategies:
    """
    Factory for standard Beam window configurations used in CDC streaming.

    Usage:
        strategy = StreamingWindowStrategies.fixed_with_early_firing(
            window_size_seconds=60,
            early_firing_seconds=10,
            allowed_lateness_seconds=300,
        )
        records | beam.WindowInto(strategy["window"], **strategy["kwargs"])
    """

    @staticmethod
    def fixed_with_early_firing(
        window_size_seconds: int = 60,
        early_firing_seconds: int = 10,
        allowed_lateness_seconds: int = 300,
    ) -> dict:
        """
        Fixed windows with early speculative firings.

        Balances latency vs completeness:
        - Window fires at watermark (complete results)
        - Also fires every `early_firing_seconds` for low-latency preview

        Returns a dict with 'window' and 'kwargs' keys for use with beam.WindowInto.
        """
        return {
            "window": FixedWindows(window_size_seconds),
            "kwargs": {
                "trigger": AfterWatermark(
                    early=AfterProcessingTime(early_firing_seconds),
                ),
                "accumulation_mode": AccumulationMode.DISCARDING,
                "allowed_lateness": allowed_lateness_seconds,
            },
        }

    @staticmethod
    def sliding(
        window_size_seconds: int = 120,
        period_seconds: int = 30,
    ) -> dict:
        """
        Sliding windows for rolling aggregations (e.g. 2-min window every 30s).

        Returns a dict with 'window' and 'kwargs' keys.
        """
        return {
            "window": SlidingWindows(window_size_seconds, period_seconds),
            "kwargs": {
                "trigger": AfterWatermark(),
                "accumulation_mode": AccumulationMode.DISCARDING,
            },
        }

    @staticmethod
    def session(
        gap_seconds: int = 300,
    ) -> dict:
        """
        Session windows grouped by inactivity gap.

        Useful for per-entity activity streams where events cluster in bursts.

        Returns a dict with 'window' and 'kwargs' keys.
        """
        return {
            "window": Sessions(gap_seconds),
            "kwargs": {
                "trigger": AfterWatermark(),
                "accumulation_mode": AccumulationMode.ACCUMULATING,
            },
        }
