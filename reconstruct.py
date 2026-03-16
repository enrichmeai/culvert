#!/usr/bin/env python3
"""Reconstruct the GCP Pipeline Reference project from PyPI packages.

Usage:
    python reconstruct.py [--dest DIR] [--index-url URL] [--version VERSION]

This script:
    1. Creates a virtual environment
    2. Installs all packages from PyPI (or a private index)
    3. Exports the full project structure (docs, infrastructure, workflows, configs)
    4. Copies source code from each reference implementation into the project layout
    5. Produces a ready-to-use project directory you can push to an internal repo

Requirements: Python 3.9+
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# All packages that make up the full project
FRAMEWORK_PACKAGE = "gcp-pipeline-framework"
REFERENCE_PACKAGES = {
    "gcp-pipeline-ref-ingestion": "original-data-to-bigqueryload",
    "gcp-pipeline-ref-transform": "bigquery-to-mapped-product",
    "gcp-pipeline-ref-orchestration": "data-pipeline-orchestrator",
    "gcp-pipeline-ref-cdp": "fdp-to-consumable-product",
    "gcp-pipeline-ref-segment-transform": "mainframe-segment-transform",
}

# Mapping of ref package name → installed top-level Python package
PACKAGE_IMPORT_MAP = {
    "gcp-pipeline-ref-ingestion": "data_ingestion",
    "gcp-pipeline-ref-transform": "dbt",
    "gcp-pipeline-ref-orchestration": "dags",
    "gcp-pipeline-ref-cdp": "dbt",
    "gcp-pipeline-ref-segment-transform": "cdp_example",
}

LIBRARY_PACKAGES = [
    "gcp-pipeline-core",
    "gcp-pipeline-beam",
    "gcp-pipeline-orchestration",
    "gcp-pipeline-transform",
    "gcp-pipeline-tester",
]


def run(cmd, **kwargs):
    """Run a command and return the result."""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, check=True, **kwargs)


def create_venv(venv_path: Path):
    """Create a virtual environment."""
    print(f"\n[1/5] Creating virtual environment at {venv_path}")
    run([sys.executable, "-m", "venv", str(venv_path)])
    return venv_path / "bin" / "pip" if os.name != "nt" else venv_path / "Scripts" / "pip.exe"


def install_packages(pip: Path, version: str | None, index_url: str | None):
    """Install all packages from PyPI."""
    print("\n[2/5] Installing packages from PyPI")

    version_spec = f"=={version}" if version else ""
    index_args = ["--index-url", index_url] if index_url else []

    # Install framework (pulls all libraries)
    run([str(pip), "install", f"{FRAMEWORK_PACKAGE}{version_spec}"] + index_args)

    # Install reference implementations
    for pkg in REFERENCE_PACKAGES:
        run([str(pip), "install", f"{pkg}{version_spec}"] + index_args)


def export_framework_assets(pip: Path, dest: Path):
    """Use the framework's export_project to extract docs, infra, workflows, configs."""
    print(f"\n[3/5] Exporting framework assets to {dest}")
    python = pip.parent / ("python" if os.name != "nt" else "python.exe")
    run([
        str(python), "-c",
        f"from gcp_pipeline_framework import export_project; export_project('{dest}')"
    ])


def extract_reference_source(pip: Path, dest: Path):
    """Copy source code from installed reference packages into deployment dirs."""
    print("\n[4/5] Extracting reference implementation source code")
    python = pip.parent / ("python" if os.name != "nt" else "python.exe")

    for pkg_name, deploy_dir in REFERENCE_PACKAGES.items():
        import_name = PACKAGE_IMPORT_MAP[pkg_name]
        deploy_path = dest / "deployments" / deploy_dir

        # Get installed package location
        result = subprocess.run(
            [str(python), "-c", f"import {import_name}; print({import_name}.__path__[0])"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  WARNING: Could not locate {pkg_name} ({import_name})")
            continue

        pkg_path = Path(result.stdout.strip())
        print(f"  {pkg_name} → {deploy_path}")

        # Determine if source uses src/ layout or flat layout
        if import_name == "data_ingestion" or import_name == "cdp_example":
            # src/ layout: copy into deployments/{dir}/src/{import_name}/
            src_dest = deploy_path / "src" / import_name
            src_dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(pkg_path, src_dest, dirs_exist_ok=True)
        elif import_name == "dags":
            # flat layout: copy into deployments/{dir}/dags/
            dags_dest = deploy_path / "dags"
            dags_dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(pkg_path, dags_dest, dirs_exist_ok=True)
        elif import_name == "dbt":
            # dbt layout: copy into deployments/{dir}/dbt/
            dbt_dest = deploy_path / "dbt"
            dbt_dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(pkg_path, dbt_dest, dirs_exist_ok=True)

        # Copy tests if available (from .dist-info or alongside package)
        tests_path = pkg_path.parent / "tests"
        if tests_path.exists():
            tests_dest = deploy_path / "tests"
            shutil.copytree(tests_path, tests_dest, dirs_exist_ok=True)

    # Also extract library source into gcp-pipeline-libraries/
    print("\n  Extracting library source code...")
    for lib in LIBRARY_PACKAGES:
        lib_import = lib.replace("-", "_")
        result = subprocess.run(
            [str(python), "-c", f"import {lib_import}; print({lib_import}.__path__[0])"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            continue

        lib_path = Path(result.stdout.strip())
        lib_dest = dest / "gcp-pipeline-libraries" / lib / "src" / lib_import
        lib_dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(lib_path, lib_dest, dirs_exist_ok=True)
        print(f"  {lib} → {lib_dest.parent.parent}")


def print_summary(dest: Path):
    """Print a summary of the reconstructed project."""
    print(f"\n[5/5] Project reconstructed at: {dest}")
    print()
    print("Directory layout:")
    for item in sorted(dest.iterdir()):
        if item.is_dir():
            count = sum(1 for _ in item.rglob("*") if _.is_file())
            print(f"  {item.name}/  ({count} files)")
        else:
            print(f"  {item.name}")

    print()
    print("Next steps:")
    print(f"  cd {dest}")
    print("  git init")
    print("  git add -A")
    print("  git commit -m 'Import GCP Pipeline Reference from PyPI'")
    print("  git remote add origin <your-internal-repo-url>")
    print("  git push -u origin main")
    print()
    print("To set up a development environment:")
    print(f"  cd {dest}")
    print("  python -m venv .venv")
    print("  source .venv/bin/activate")
    print("  pip install gcp-pipeline-framework[tester]")
    print("  pip install -e deployments/original-data-to-bigqueryload[dev]")


def main():
    parser = argparse.ArgumentParser(
        description="Reconstruct the GCP Pipeline Reference project from PyPI packages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reconstruct from public PyPI
  python reconstruct.py

  # Reconstruct a specific version
  python reconstruct.py --version 1.0.11

  # Reconstruct from a private index (Nexus, Artifactory, etc.)
  python reconstruct.py --index-url https://nexus.internal/repository/pypi/simple/

  # Specify output directory
  python reconstruct.py --dest /path/to/my-project
        """,
    )
    parser.add_argument(
        "--dest", default="gcp-pipeline-reference",
        help="Destination directory for the reconstructed project (default: gcp-pipeline-reference)",
    )
    parser.add_argument(
        "--index-url",
        help="PyPI index URL (for private registries like Nexus or Artifactory)",
    )
    parser.add_argument(
        "--version",
        help="Specific version to install (e.g. 1.0.11). Default: latest.",
    )
    parser.add_argument(
        "--keep-venv", action="store_true",
        help="Keep the temporary venv after reconstruction (for debugging)",
    )

    args = parser.parse_args()
    dest = Path(args.dest).resolve()

    if dest.exists() and any(dest.iterdir()):
        print(f"ERROR: {dest} already exists and is not empty.", file=sys.stderr)
        sys.exit(1)

    # Use a temp venv for installation
    with tempfile.TemporaryDirectory(prefix="gcp-pipeline-venv-") as tmp:
        venv_path = Path(tmp) / "venv"
        pip = create_venv(venv_path)
        install_packages(pip, args.version, args.index_url)
        export_framework_assets(pip, dest)
        extract_reference_source(pip, dest)

        if args.keep_venv:
            permanent_venv = dest / ".venv"
            shutil.copytree(venv_path, permanent_venv)
            print(f"\n  Venv preserved at {permanent_venv}")

    print_summary(dest)


if __name__ == "__main__":
    main()
