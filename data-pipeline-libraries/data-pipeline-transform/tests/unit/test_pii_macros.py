import os
import subprocess
import json
import pytest

def test_pii_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt compile
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    dbt_executable = "dbt"
    # In some environments (like local venv), dbt might not be in PATH but in venv/bin
    if not any(os.access(os.path.join(path, dbt_executable), os.X_OK) for path in os.environ.get("PATH", "").split(os.pathsep)):
        # Try to find it relative to the python executable
        import sys
        venv_bin = os.path.dirname(sys.executable)
        venv_dbt = os.path.join(venv_bin, dbt_executable)
        if os.path.exists(venv_dbt):
            dbt_executable = venv_dbt

    # Use dbt parse instead of compile to avoid GCP authentication issues in CI
    # parse still generates the manifest.json and ensures macros are syntactically correct
    result = subprocess.run(
        [dbt_executable, "parse", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0, f"dbt parse failed: {result.stdout} {result.stderr}"

    # After parse, we can check the manifest.json for macro definitions or other metadata
    manifest_path = os.path.join(project_dir, "target/manifest.json")
    assert os.path.exists(manifest_path), "dbt manifest.json not found"
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Verify macros exist in manifest
    macros = manifest.get("macros", {})
    macro_names = [m.split(".")[-1] for m in macros.keys()]
    assert "mask_full" in macro_names
    assert "mask_redacted" in macro_names
    assert "mask_partial_last4" in macro_names
    assert "mask_pii" in macro_names

def test_audit_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt parse
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    dbt_executable = "dbt"
    if not any(os.access(os.path.join(path, dbt_executable), os.X_OK) for path in os.environ.get("PATH", "").split(os.pathsep)):
        import sys
        venv_bin = os.path.dirname(sys.executable)
        venv_dbt = os.path.join(venv_bin, dbt_executable)
        if os.path.exists(venv_dbt):
            dbt_executable = venv_dbt

    result = subprocess.run(
        [dbt_executable, "parse", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0, f"dbt parse failed: {result.stdout} {result.stderr}"

    manifest_path = os.path.join(project_dir, "target/manifest.json")
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    macros = manifest.get("macros", {})
    macro_names = [m.split(".")[-1] for m in macros.keys()]
    assert "add_audit_columns" in macro_names
    assert "apply_audit_columns" in macro_names

def test_dq_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt parse
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    dbt_executable = "dbt"
    if not any(os.access(os.path.join(path, dbt_executable), os.X_OK) for path in os.environ.get("PATH", "").split(os.pathsep)):
        import sys
        venv_bin = os.path.dirname(sys.executable)
        venv_dbt = os.path.join(venv_bin, dbt_executable)
        if os.path.exists(venv_dbt):
            dbt_executable = venv_dbt

    result = subprocess.run(
        [dbt_executable, "parse", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0, f"dbt parse failed: {result.stdout} {result.stderr}"

    manifest_path = os.path.join(project_dir, "target/manifest.json")
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    macros = manifest.get("macros", {})
    macro_names = [m.split(".")[-1] for m in macros.keys()]
    assert "check_required_fields" in macro_names
    assert "check_uniqueness" in macro_names

def test_enrichment_macros_compilation():
    # Detect if we are running from project root or library root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(base_dir, "dbt_test_project")

    # Run dbt parse
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = project_dir
    dbt_executable = "dbt"
    if not any(os.access(os.path.join(path, dbt_executable), os.X_OK) for path in os.environ.get("PATH", "").split(os.pathsep)):
        import sys
        venv_bin = os.path.dirname(sys.executable)
        venv_dbt = os.path.join(venv_bin, dbt_executable)
        if os.path.exists(venv_dbt):
            dbt_executable = venv_dbt

    result = subprocess.run(
        [dbt_executable, "parse", "--project-dir", project_dir, "--profiles-dir", project_dir, "--target", "dev"],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0, f"dbt parse failed: {result.stdout} {result.stderr}"

    manifest_path = os.path.join(project_dir, "target/manifest.json")
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    macros = manifest.get("macros", {})
    macro_names = [m.split(".")[-1] for m in macros.keys()]
    assert "apply_enrichment" in macro_names

if __name__ == "__main__":
    test_pii_macros_compilation()
    test_audit_macros_compilation()
    test_dq_macros_compilation()
    test_enrichment_macros_compilation()
