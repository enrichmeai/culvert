# Python Context Help and Standards

## Overview
This document defines Python coding standards, documentation patterns, and environment setups to ensure optimal "Context Help" and IDE (e.g., PyCharm, IntelliJ) integration. Following these rules allows editors to provide better error detection, type-ahead completion, and inline documentation.

## IDE Integration & Environment Setup
To enable full cross-module context help and error detection, the IDE must be able to resolve all internal dependencies.

1.  **Recommended Setup**: Use the root-level `pyproject.toml` to install all libraries and deployments in "editable mode". This ensures changes in `gcp-pipeline-libraries/` are immediately reflected in `deployments/`.
    ```bash
    # From project root
    pip install -e .[dev]
    ```
2.  **Virtual Environment**: A single virtual environment at the root is recommended for full-project analysis.

## Documentation Standards (Google-style)
Use Google-style docstrings for all classes and functions. This provides the best "Hover Help" in modern IDEs.

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief summary of the function.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of the return value.
    """
```

## Type Hinting
Mandatory type hints for all function signatures and complex class attributes. This enables the editor to provide "Context Help" regarding available methods and properties.

-   Use `from typing import ...` for complex types (List, Dict, Optional, etc.).
-   Use Python 3.9+ native types where possible (`list[str]`, `dict[str, int]`).

## Library Imports
-   **Always** import from the top-level package names (e.g., `from gcp_pipeline_core.monitoring import ...`).
-   Avoid relative imports (`from .. import ...`) as they can break context help when modules are installed in editable mode.

## Project Structure Awareness
-   `gcp-pipeline-libraries/`: Shared code. Changes here affect all deployments.
-   `deployments/`: System-specific logic. Dependencies on libraries are declared in `pyproject.toml`.

## Python Version
-   **Target: Python 3.11**. The CI pipeline and local dev both use `python3.11`.
-   Do **not** use `datetime.utcnow()` — deprecated in 3.12. Use `datetime.now(tz=timezone.utc)`.
-   Do **not** use `datetime.utcfromtimestamp(ts)`. Use `datetime.fromtimestamp(ts, tz=timezone.utc)`.

## Logging Rules
-   All operational output goes through `logging`. **Never use `print()`** in library code.
-   Logger per module: `logger = logging.getLogger(__name__)`
-   Pass structured data as the second arg, not as `**kwargs`: `logger.warning("msg: %s", data_dict)`
    -   `logger.warning("Reconciliation failed", **data)` → **TypeError at runtime**
    -   `logger.warning("Reconciliation failed: %s", data)` → correct

## Library Boundary Rules
-   `gcp-pipeline-core`: MUST NOT import `apache_beam` or `apache_airflow`
-   `gcp-pipeline-beam`: MUST NOT import `apache_airflow`
-   `gcp-pipeline-orchestration`: MUST NOT import `apache_beam`
-   DoFns MUST route errors to tagged outputs — never raise inside `process()`

## Error Handling Patterns

```python
# Right: route to tagged output
def process(self, element):
    try:
        yield self._parse(element)
    except Exception as exc:
        logger.error("Parse failed: %s", exc)
        yield beam.pvalue.TaggedOutput("errors", {"raw": element, "error": str(exc)})

# Wrong: raises inside process — kills the bundle
def process(self, element):
    result = self._parse(element)  # raises on bad input
    yield result
```

## See Also
-   [testing.md](.junie/guidelines/testing.md) — Test standards, fixture design, mock scope rules
