"""
CLI for gcp-pipeline-ref-ingestion reference implementation.

Provides commands to:
- Extract reference source code to a local directory
- Show package info and structure
- Run the pipeline (if configured)

Usage:
    gcp-ref-ingestion extract ./my-project
    gcp-ref-ingestion info
"""

import argparse
import shutil
import sys
from pathlib import Path
from importlib import resources


def get_package_root() -> Path:
    """Get the root path of the installed package."""
    # In Python 3.9+, use importlib.resources
    try:
        with resources.as_file(resources.files("data_ingestion")) as pkg_path:
            return pkg_path
    except (TypeError, AttributeError):
        # Fallback for older Python or editable installs
        return Path(__file__).parent


def cmd_info(args: argparse.Namespace) -> int:
    """Show package information and structure."""
    from data_ingestion import __version__

    pkg_root = get_package_root()

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║  gcp-pipeline-ref-ingestion v{__version__:<30} ║
║  Reference Implementation: GCS-to-BigQuery Ingestion         ║
╚═══════════════════════════════════════════════════════════════╝

📦 Package Location: {pkg_root}

📁 Structure:
""")

    def print_tree(path: Path, prefix: str = ""):
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, entry in enumerate(entries):
            if entry.name.startswith("__pycache__"):
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            print(f"    {prefix}{connector}{entry.name}")
            if entry.is_dir() and not entry.name.startswith("__"):
                extension = "    " if i == len(entries) - 1 else "│   "
                print_tree(entry, prefix + extension)

    print_tree(pkg_root)

    print("""
🚀 Quick Start:
    # Extract reference code to your project
    gcp-ref-ingestion extract ./my-ingestion-pipeline
    
    # Then customize for your use case
    cd my-ingestion-pipeline
    
📚 Documentation:
    https://github.com/enrichmeai/gcp-pipeline-reference

💡 This reference shows:
    - HDR/TRL file parsing
    - Schema-driven validation  
    - Multi-entity JOIN pattern
    - Audit trail integration
""")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract reference source code to target directory."""
    target = Path(args.target).resolve()
    pkg_root = get_package_root()

    if target.exists() and not args.force:
        print(f"❌ Target directory already exists: {target}")
        print("   Use --force to overwrite")
        return 1

    print(f"📦 Extracting reference code to: {target}")

    # Create target directory
    target.mkdir(parents=True, exist_ok=True)

    # Copy source files
    src_target = target / "src" / "data_ingestion"
    if src_target.exists() and args.force:
        shutil.rmtree(src_target)

    shutil.copytree(
        pkg_root,
        src_target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache")
    )

    # Create a minimal pyproject.toml for the extracted project
    pyproject_content = '''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-ingestion-pipeline"
version = "0.1.0"
description = "My GCS-to-BigQuery Ingestion Pipeline (based on gcp-pipeline-ref-ingestion)"
requires-python = ">=3.9"
dependencies = [
    "google-cloud-bigquery>=3.0.0",
    "google-cloud-storage>=2.0.0",
    "pydantic>=2.0.0",
    "gcp-pipeline-framework[core,beam]>=1.0.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
    "gcp-pipeline-tester>=1.0.7",
]

[tool.setuptools.packages.find]
where = ["src"]
'''

    (target / "pyproject.toml").write_text(pyproject_content)

    # Create a README
    readme_content = '''# My Ingestion Pipeline

This project was scaffolded from `gcp-pipeline-ref-ingestion`.

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run pipeline (update config first)
python -m data_ingestion.pipeline.run --entity customers
```

## Customization

1. Update `src/data_ingestion/config/` with your GCP project settings
2. Modify schemas in `src/data_ingestion/schema/`
3. Adjust validation rules in `src/data_ingestion/validation/`

## Documentation

See: https://github.com/enrichmeai/gcp-pipeline-reference
'''

    (target / "README.md").write_text(readme_content)

    # Create tests directory
    tests_dir = target / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "__init__.py").touch()

    print(f"""
✅ Reference code extracted successfully!

📁 Created:
    {target}/
    ├── pyproject.toml
    ├── README.md
    ├── src/
    │   └── data_ingestion/
    │       ├── config/
    │       ├── pipeline/
    │       ├── schema/
    │       └── validation/
    └── tests/

🚀 Next steps:
    cd {target}
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
""")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="gcp-ref-ingestion",
        description="GCP Pipeline Reference Implementation: GCS-to-BigQuery Ingestion"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # info command
    info_parser = subparsers.add_parser("info", help="Show package info and structure")
    info_parser.set_defaults(func=cmd_info)

    # extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract reference source code to a directory"
    )
    extract_parser.add_argument(
        "target",
        help="Target directory to extract code to"
    )
    extract_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing directory"
    )
    extract_parser.set_defaults(func=cmd_extract)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

