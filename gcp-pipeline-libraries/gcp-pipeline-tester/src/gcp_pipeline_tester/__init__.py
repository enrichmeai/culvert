"""DEPRECATED — `gcp-pipeline-tester` has been renamed to `data-pipeline-tester`.

This package is a thin deprecation shim that re-exports everything from
the renamed `data_pipeline_tester` distribution. It exists only to keep
existing `import gcp_pipeline_tester` statements working for one release
cycle so downstream consumers can migrate at their own pace.

Migration:

    # before
    from gcp_pipeline_tester import BasePipelineTest
    from gcp_pipeline_tester.builders import RecordBuilder

    # after
    from data_pipeline_tester import BasePipelineTest
    from data_pipeline_tester.builders import RecordBuilder

The shim will be removed in a future release. See
`docs/framework-evolution/02-redesign.md` for the renaming rationale and
the full Stage 1 migration plan.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "`gcp_pipeline_tester` is renamed to `data_pipeline_tester`. "
    "Update your imports: `from gcp_pipeline_tester...` -> "
    "`from data_pipeline_tester...`. This shim will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the renamed distribution. Each submodule
# is exposed as an attribute so existing
# `from gcp_pipeline_tester.builders import X` continues to resolve.
from data_pipeline_tester import (
    BaseBeamTest,
    BasePipelineTest,
    BaseValidationTest,
    ComparisonReport,
    ComparisonResult,
    DualRunComparison,
    PipelineScenarioTest,
    TestResult,
)

# Submodule re-exports so dotted imports keep working.
from data_pipeline_tester import (  # noqa: F401
    assertions,
    base,
    bdd,
    builders,
    comparison,
    fixtures,
    mocks,
)

__version__ = "2.0.0"

__all__ = [
    "__version__",
    "TestResult",
    "BasePipelineTest",
    "BaseValidationTest",
    "BaseBeamTest",
    "PipelineScenarioTest",
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
    "assertions",
    "base",
    "bdd",
    "builders",
    "comparison",
    "fixtures",
    "mocks",
]
