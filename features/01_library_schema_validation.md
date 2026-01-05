# Prompt: Library Enhancement - Schema-Driven Validation

**STATUS: ✅ COMPLETE**

## Context
The `gcp-pipeline-builder` library contains an `EntitySchema` class and a generic `ValidateRecordDoFn`. However, they are currently disconnected. Pipelines must manually implement validation logic even though the schema already defines requirements like `required`, `allowed_values`, and `max_length`.

## What Was Implemented

### 1. SchemaValidator Class ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/validators/schema_validator.py`

- Validates records against EntitySchema automatically
- Checks: required fields, allowed values, max length, type consistency
- Masks PII fields in error messages (for `is_pii=True` fields)
- Returns list of validation errors
- 20 unit tests passing

### 2. SchemaValidateRecordDoFn ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/validators.py`

- Beam DoFn that uses SchemaValidator
- Routes valid records to main output, invalid to 'invalid' tagged output
- Includes record and errors in invalid output

### 3. EM Pipeline Integration ✅
**File:** `deployments/em/src/em/pipeline/em_pipeline.py`

```python
from gcp_pipeline_builder.pipelines.beam.transforms import SchemaValidateRecordDoFn

# Validate using SCHEMA-DRIVEN validation from library
validated = records | 'Validate' >> beam.ParDo(
    SchemaValidateRecordDoFn(schema=schema)
).with_outputs('invalid', main='valid')
```

### 4. LOA Pipeline Integration ✅
**File:** `deployments/loa/src/loa/pipeline/loa_pipeline.py`

Same pattern as EM - uses SchemaValidateRecordDoFn.

---

## Usage Guide

### Basic Usage
```python
from gcp_pipeline_builder.validators import SchemaValidator
from my_deployment.schema import MyEntitySchema

validator = SchemaValidator(MyEntitySchema)

record = {"id": "123", "name": "Test", "status": "ACTIVE"}
errors = validator.validate(record)

if errors:
    print(f"Validation failed: {errors}")
else:
    print("Record is valid")
```

### In Beam Pipeline
```python
from gcp_pipeline_builder.pipelines.beam.transforms import SchemaValidateRecordDoFn

validated = records | 'Validate' >> beam.ParDo(
    SchemaValidateRecordDoFn(schema=MyEntitySchema)
).with_outputs('invalid', main='valid')

# Process valid records
validated.valid | 'WriteValid' >> beam.io.WriteToBigQuery(...)

# Process invalid records
validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(...)
```

---

## Validation Checks

| Check | Schema Field | Example |
|-------|--------------|---------|
| Required | `required=True` | Field must be present and non-empty |
| Allowed Values | `allowed_values=['A', 'B']` | Value must be in list |
| Max Length | `max_length=50` | String length ≤ max_length |
| Type Consistency | `field_type='INTEGER'` | Value can be cast to type |

---

## PII Masking in Errors

For fields marked `is_pii=True`, values are masked in error messages:

```python
# Schema defines: ssn field with is_pii=True
# Invalid SSN value: "123-45-6789"

# Error message shows:
"Field 'ssn' value '***MASKED***' is not in allowed values"
```

---

## Test Results

```
tests/unit/validators/test_schema_validator.py - 20 tests passed ✅
```

---

## Files Modified

| File | Change |
|------|--------|
| `validators/schema_validator.py` | Created SchemaValidator class |
| `validators/__init__.py` | Added SchemaValidator export |
| `transforms/validators.py` | Added SchemaValidateRecordDoFn |
| `em/pipeline/em_pipeline.py` | Uses SchemaValidateRecordDoFn |
| `loa/pipeline/loa_pipeline.py` | Uses SchemaValidateRecordDoFn |
