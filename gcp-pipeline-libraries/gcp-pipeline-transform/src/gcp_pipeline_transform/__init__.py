"""DEPRECATED -- `gcp-pipeline-transform` has been renamed to `data-pipeline-transform`.

This package is a thin deprecation shim that re-exports the renamed
`data_pipeline_transform` distribution. The Python module itself contains
no logic (the package is dbt-SQL only); installing `data-pipeline-transform`
gives you the same macro library under the new name.

Migration:

    # before
    pip install gcp-pipeline-transform

    # after
    pip install data-pipeline-transform

The shim will be removed in a future release. See
`docs/framework-evolution/02-redesign.md` for the rename rationale.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "`gcp_pipeline_transform` is renamed to `data_pipeline_transform`. "
    "Update your dependency to `data-pipeline-transform` and your imports "
    "to `data_pipeline_transform.*`. This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the renamed module's surface. The Python package is essentially
# empty (real content is the dbt macros under src/data_pipeline_transform/dbt_shared/macros/),
# so there's nothing structural to re-export. This shim exists to give
# downstream code a soft-failure migration path.
try:
    from data_pipeline_transform import *  # noqa: F401, F403
    from data_pipeline_transform import __version__ as _DPT_VERSION
    __version__ = "2.0.0"
except ImportError:
    __version__ = "2.0.0"
