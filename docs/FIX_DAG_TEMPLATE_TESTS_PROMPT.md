# Fix DAG Template Tests Prompt

**Status:** Ready for Implementation  
**Created:** January 2, 2026  
**Target File:** `deployments/em/tests/unit/pipeline/test_dag_template.py`

---

## Problem Statement

Two tests in `test_dag_template.py` are currently skipped because the `validate_input_files` function performs **local imports** inside the function body, making them difficult to mock:

```python
@pytest.mark.skip(reason="Requires complex mocking of local imports...")
def test_validate_input_files_success():
    pass

@pytest.mark.skip(reason="Requires complex mocking of local imports...")
def test_validate_input_files_format_failure():
    pass
```

### Root Cause

In `deployments/em/pipeline/dag_template.py`, the `validate_input_files` function imports modules **inside** the function:

```python
def validate_input_files(job_name: str, input_pattern: str, **context) -> Dict[str, Any]:
    # Library imports (INSIDE function - hard to mock)
    from gdw_data_core.core import GCSClient, discover_split_files
    from gdw_data_core.core.file_management import FileValidator
    from gdw_data_core.orchestration.callbacks import on_validation_failure

    # EM-specific imports (INSIDE function - hard to mock)
    from deployments.em.pipeline.pipeline_router import PipelineRouter
    from deployments.em.validation import EMValidator
    from deployments.em.schema import EM_SCHEMAS
    ...
```

When patching with `@patch('deployments.em.validation.EMValidator')`, the mock doesn't take effect because the import happens at runtime inside the function.

---

## Solution Options

### Option 1: Refactor `validate_input_files` to Use Top-Level Imports (Recommended)

**Change:** Move imports to the top of `dag_template.py` module.

**Pros:**
- Standard Python practice
- Easy to mock in tests
- Better IDE support (autocomplete, type hints)

**Cons:**
- Slightly longer import time at module load
- May cause circular import issues (need to verify)

**Implementation:**

```python
# dag_template.py - Move imports to top level

# At top of file, add:
from gdw_data_core.core import GCSClient, discover_split_files
from gdw_data_core.core.file_management import FileValidator
from gdw_data_core.orchestration.callbacks import on_validation_failure
from deployments.em.pipeline.pipeline_router import PipelineRouter
from deployments.em.validation import EMValidator
from deployments.em.schema import EM_SCHEMAS

# Then in function, remove local imports:
def validate_input_files(job_name: str, input_pattern: str, **context) -> Dict[str, Any]:
    # No more local imports needed
    try:
        parts = input_pattern.replace("gs://", "").split("/")
        ...
```

---

### Option 2: Use `importlib` Patching

**Change:** Patch `sys.modules` before calling the function.

**Pros:**
- No changes to source code
- Works with local imports

**Cons:**
- Complex test setup
- Fragile - depends on import order

**Implementation:**

```python
def test_validate_input_files_success():
    """Test successful file validation."""
    # Create mock objects
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = ["customers_20250101.csv"]
    mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\n..."
    
    mock_validator = MagicMock()
    mock_validator.validate_file.return_value = MagicMock(is_valid=True, errors=[])
    
    mock_router = MagicMock()
    mock_router.detect_file_type.return_value = "customers"
    mock_router.validate_file_structure.return_value = (True, [])
    
    # Patch at the source modules before function imports them
    with patch.dict('sys.modules', {
        'gdw_data_core.core': MagicMock(
            GCSClient=MagicMock(return_value=mock_gcs),
            discover_split_files=MagicMock(return_value=["group1"])
        ),
        'deployments.em.validation': MagicMock(EMValidator=MagicMock(return_value=mock_validator)),
        'deployments.em.pipeline.pipeline_router': MagicMock(PipelineRouter=MagicMock(return_value=mock_router)),
    }):
        # Re-import to get fresh module with mocked dependencies
        import importlib
        import deployments.em.pipeline.dag_template as dag_module
        importlib.reload(dag_module)
        
        result = dag_module.validate_input_files("customers", "gs://bucket/prefix/*.csv")
        
        assert result["status"] == "ready"
```

---

### Option 3: Create Wrapper Function for Dependency Injection (Best Practice)

**Change:** Refactor to accept dependencies as optional parameters.

**Pros:**
- Clean, testable code
- No mocking complexity
- Follows dependency injection pattern

**Cons:**
- Requires refactoring source code

**Implementation:**

```python
# dag_template.py

def validate_input_files(
    job_name: str, 
    input_pattern: str, 
    gcs_client=None,
    validator=None,
    router=None,
    **context
) -> Dict[str, Any]:
    """
    Validate input files for processing.
    
    Args:
        job_name: Entity name
        input_pattern: GCS path pattern
        gcs_client: Optional GCSClient (for testing)
        validator: Optional EMValidator (for testing)
        router: Optional PipelineRouter (for testing)
    """
    # Use injected dependencies or create defaults
    if gcs_client is None:
        from gdw_data_core.core import GCSClient
        gcs_client = GCSClient(project=DEFAULT_PROJECT_ID)
    
    if validator is None:
        from deployments.em.validation import EMValidator
        validator = EMValidator()
    
    if router is None:
        from deployments.em.pipeline.pipeline_router import PipelineRouter
        router = PipelineRouter()
    
    # Rest of function uses injected dependencies
    ...
```

Then tests become simple:

```python
def test_validate_input_files_success():
    mock_gcs = MagicMock()
    mock_gcs.list_files.return_value = ["file.csv"]
    mock_gcs.read_file.return_value = "HDR|EM|customers|20250101\n..."
    
    mock_validator = MagicMock()
    mock_validator.validate_file.return_value = MagicMock(is_valid=True, errors=[])
    
    mock_router = MagicMock()
    mock_router.validate_file_structure.return_value = (True, [])
    
    result = validate_input_files(
        "customers", 
        "gs://bucket/*.csv",
        gcs_client=mock_gcs,
        validator=mock_validator,
        router=mock_router
    )
    
    assert result["status"] == "ready"
```

---

## Recommended Approach

**Use Option 3 (Dependency Injection)** for these reasons:

1. **Clean separation** - Production code doesn't change behavior
2. **Easy testing** - No complex mocking required
3. **Explicit dependencies** - Clear what the function needs
4. **Backwards compatible** - Default behavior unchanged

---

## Implementation Checklist

### Step 1: Refactor `dag_template.py`

- [ ] Update `validate_input_files` signature to accept optional dependencies
- [ ] Add lazy imports for default values
- [ ] Keep existing behavior when dependencies not provided

### Step 2: Update Tests

- [ ] Remove `@pytest.mark.skip` decorators
- [ ] Create mock objects for GCSClient, EMValidator, PipelineRouter
- [ ] Pass mocks as parameters to `validate_input_files`
- [ ] Add assertions for expected behavior

### Step 3: Verify

- [ ] Run tests locally: `pytest deployments/em/tests/unit/pipeline/test_dag_template.py -v`
- [ ] Ensure no skipped tests
- [ ] Commit and push to trigger CI

---

## Test Cases to Implement

| Test | Description | Expected Result |
|------|-------------|-----------------|
| `test_validate_input_files_success` | Valid HDR/TRL file, all validations pass | `{"status": "ready", "file_count": 1, ...}` |
| `test_validate_input_files_format_failure` | Invalid file format | Raises `AirflowException` with "File format check failed" |
| `test_validate_input_files_no_files` | No matching files | Raises `AirflowException` with "No input files found" |
| `test_validate_input_files_validation_failure` | EMValidator returns errors | Raises `AirflowException` with validation errors |

---

## Files to Modify

1. `deployments/em/pipeline/dag_template.py` - Add dependency injection
2. `deployments/em/tests/unit/pipeline/test_dag_template.py` - Implement tests

---

## Approval Required

Before implementing, confirm:
- [ ] Option 3 (Dependency Injection) is acceptable
- [ ] Modifying `dag_template.py` signature is allowed
- [ ] No downstream code depends on current signature

