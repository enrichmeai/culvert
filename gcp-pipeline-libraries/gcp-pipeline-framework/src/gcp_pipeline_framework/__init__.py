"""DEPRECATED -- `gcp-pipeline-framework` has been renamed to `data-pipeline-framework`.

This package is a thin deprecation shim that re-exports the renamed
`data_pipeline_framework` distribution. Installing `data-pipeline-framework`
gives you the umbrella metapackage under the new name.

Migration:

    # before
    pip install gcp-pipeline-framework
    from gcp_pipeline_framework import export_project, get_docs_path

    # after
    pip install data-pipeline-framework
    from data_pipeline_framework import export_project, get_docs_path

The renamed package also installs a `data-pipeline-docs` CLI entry point
(previously `gcp-pipeline-docs`). The shim will be removed in a future
release. See `docs/framework-evolution/02-redesign.md` for rationale.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "`gcp_pipeline_framework` is renamed to `data_pipeline_framework`. "
    "Update your imports: `from gcp_pipeline_framework...` -> "
    "`from data_pipeline_framework...`. This shim will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

from data_pipeline_framework import (  # noqa: F401
    export_project,
    get_config_path,
    get_deployments_path,
    get_docs_path,
    get_infrastructure_path,
    get_test_data_path,
    get_workflows_path,
    list_docs,
)

__version__ = "2.0.0"
