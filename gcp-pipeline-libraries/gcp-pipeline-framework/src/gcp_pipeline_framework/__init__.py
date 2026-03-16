"""GCP Pipeline Framework — umbrella package for all pipeline libraries."""

from importlib import resources
from pathlib import Path


def _package_root() -> Path:
    """Return the root path of the installed gcp_pipeline_framework package."""
    return Path(resources.files("gcp_pipeline_framework"))


def get_docs_path() -> Path:
    """Return the path to bundled documentation files."""
    return _package_root() / "docs"


def get_infrastructure_path() -> Path:
    """Return the path to bundled infrastructure files (Terraform, K8s)."""
    return _package_root() / "infrastructure"


def get_workflows_path() -> Path:
    """Return the path to bundled GitHub Actions workflow files."""
    return _package_root() / "workflows"


def get_config_path() -> Path:
    """Return the path to bundled root config files."""
    return _package_root() / "config"


def get_deployments_path() -> Path:
    """Return the path to bundled deployment configs (Dockerfiles, cloudbuild)."""
    return _package_root() / "deployments"


def list_docs() -> list[str]:
    """List all bundled documentation files."""
    return sorted(f.name for f in get_docs_path().glob("*.md"))


def export_project(dest: str = "gcp-pipeline-reference") -> Path:
    """Export the full project structure to a destination directory.

    Recreates the repo layout:
        dest/
            docs/
            infrastructure/
            .github/workflows/
            deployments/  (Dockerfiles, cloudbuild, pyproject.toml, README)
            .gitignore, .dockerignore, etc.

    Args:
        dest: Target directory (created if it doesn't exist).

    Returns:
        Path to the destination directory.
    """
    import shutil

    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    # Docs → dest/docs/
    _copy_tree(get_docs_path(), dest_path / "docs")

    # Infrastructure → dest/infrastructure/
    _copy_tree(get_infrastructure_path(), dest_path / "infrastructure")

    # Workflows → dest/.github/workflows/
    _copy_tree(get_workflows_path(), dest_path / ".github" / "workflows")

    # Deployments → dest/deployments/
    _copy_tree(get_deployments_path(), dest_path / "deployments")

    # Config → dest/ (root-level files, restore dotfile names)
    config_path = get_config_path()
    if config_path.exists():
        dotfile_renames = {"gitignore": ".gitignore", "dockerignore": ".dockerignore", "gcloudignore": ".gcloudignore"}
        for f in config_path.iterdir():
            if f.is_file():
                target_name = dotfile_renames.get(f.name, f.name)
                shutil.copy2(f, dest_path / target_name)

    return dest_path


def _copy_tree(src: Path, dest: Path) -> None:
    """Recursively copy a directory tree."""
    import shutil

    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.name == "__init__.py" or item.name.endswith(".pyc"):
            continue
        rel = item.relative_to(src)
        if item.is_dir():
            (dest / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest / rel)
