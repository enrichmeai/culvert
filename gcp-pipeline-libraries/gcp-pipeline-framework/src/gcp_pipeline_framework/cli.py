"""CLI for GCP Pipeline Framework — list, view, and export bundled project assets."""

import argparse
import sys

from . import export_project, get_docs_path, list_docs


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gcp-pipeline-docs",
        description="Access GCP Pipeline Framework documentation and project assets bundled with the package.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all bundled documentation files")

    show_parser = sub.add_parser("show", help="Print a documentation file to stdout")
    show_parser.add_argument("filename", help="Documentation filename (e.g. DEVELOPER_TESTING_GUIDE.md)")

    export_docs_parser = sub.add_parser("export-docs", help="Export docs to a local directory")
    export_docs_parser.add_argument("--dest", default="docs", help="Destination directory (default: docs)")

    export_project_parser = sub.add_parser(
        "export-project",
        help="Export the full project structure (docs, infrastructure, workflows, deployment configs)",
    )
    export_project_parser.add_argument(
        "--dest", default="gcp-pipeline-reference", help="Destination directory (default: gcp-pipeline-reference)"
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        for name in list_docs():
            print(name)

    elif args.command == "show":
        doc = get_docs_path() / args.filename
        if not doc.exists():
            print(f"Not found: {args.filename}", file=sys.stderr)
            print(f"Available: {', '.join(list_docs())}", file=sys.stderr)
            sys.exit(1)
        print(doc.read_text())

    elif args.command == "export-docs":
        from . import _copy_tree

        dest = args.dest
        from pathlib import Path

        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        _copy_tree(get_docs_path(), dest_path)
        print(f"Exported {len(list_docs())} docs to {dest}/")

    elif args.command == "export-project":
        dest_path = export_project(args.dest)
        print(f"Exported full project structure to {dest_path}/")
        print()
        print("Exported layout:")
        print(f"  {dest_path}/docs/              — All documentation guides")
        print(f"  {dest_path}/infrastructure/     — Terraform and K8s configs")
        print(f"  {dest_path}/.github/workflows/  — CI/CD pipeline definitions")
        print(f"  {dest_path}/deployments/         — Dockerfiles, cloudbuild, pyproject.toml per deployment")
        print(f"  {dest_path}/.gitignore, etc.     — Root config files")
        print()
        print("Next steps:")
        print("  1. cd", dest_path)
        print("  2. git init && git add -A && git commit -m 'Initial import from gcp-pipeline-framework'")
        print("  3. pip install gcp-pipeline-ref-ingestion gcp-pipeline-ref-transform gcp-pipeline-ref-orchestration")
        print("     (to get the full source code for each deployment)")

    else:
        parser.print_help()
