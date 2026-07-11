"""Hatchling build hook: locate the library packages in either context.

The wheel is built from two places:
  - the repo (CI / local): packages live at ../data-pipeline-libraries/*/src/
  - an extracted sdist (pip building from source): packages were packed into
    this project's own src/ by the sdist force-include

A static [tool.hatch.build.targets.wheel.force-include] can only express one
of those, so this hook resolves each package at build time.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# import package -> distribution dir under data-pipeline-libraries/
PACKAGES = {
    "data_pipeline_core": "data-pipeline-core",
    "data_pipeline_gcp_bigquery": "data-pipeline-gcp-bigquery",
    "data_pipeline_gcp_gcs": "data-pipeline-gcp-gcs",
    "data_pipeline_gcp_pubsub": "data-pipeline-gcp-pubsub",
    "data_pipeline_gcp_secrets": "data-pipeline-gcp-secrets",
    "data_pipeline_gcp_observability": "data-pipeline-gcp-observability",
    "data_pipeline_orchestration": "data-pipeline-orchestration",
    "data_pipeline_transform": "data-pipeline-transform",
    "data_pipeline_tester": "data-pipeline-tester",
    "data_pipeline_contract_tests": "data-pipeline-contract-tests",
}


class LibraryPackagesHook(BuildHookInterface):
    PLUGIN_NAME = "library-packages"

    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        force_include = build_data.setdefault("force_include", {})
        for pkg, dist in PACKAGES.items():
            repo_src = root.parent / "data-pipeline-libraries" / dist / "src" / pkg
            sdist_src = root / "src" / pkg
            src = repo_src if repo_src.is_dir() else sdist_src
            if not src.is_dir():
                raise FileNotFoundError(
                    f"package {pkg} not found at {repo_src} or {sdist_src}")
            force_include[str(src)] = pkg
