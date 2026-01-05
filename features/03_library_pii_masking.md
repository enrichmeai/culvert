# Prompt: Library Enhancement - Schema-Driven PII Masking

**STATUS: ✅ COMPLETE** (Implemented as part of SchemaValidator)

## Context
Data privacy is critical in migration projects. The `EntitySchema` includes an `is_pii` flag on `SchemaField` to mark sensitive fields. PII masking is automatically applied during validation - no separate transform needed.

## What Was Implemented

### Configuration via Schema ✅
PII masking is configured per-field using the `is_pii=True` flag:

```python
from gcp_pipeline_builder.schema import EntitySchema, SchemaField

CustomerSchema = EntitySchema(
    entity_name="customers",
    system_id="EM",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="customer_name", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", required=True, is_pii=True),  # PII
        SchemaField(name="email", field_type="STRING", is_pii=True),  # PII
        SchemaField(name="phone", field_type="STRING", is_pii=True),  # PII
        SchemaField(name="status", field_type="STRING", allowed_values=["ACTIVE", "CLOSED"]),
    ],
    primary_key=["customer_id"],
)
```

### Automatic Masking in Validation ✅
When validation fails for a PII field, the value is automatically masked in error messages:

```python
from gcp_pipeline_builder.validators import SchemaValidator

validator = SchemaValidator(CustomerSchema)

# Invalid record with PII
record = {
    "customer_id": "CUST001",
    "customer_name": "John Doe",
    "ssn": "123-45-6789",  # Invalid format
    "status": "INVALID"
}

errors = validator.validate(record)
for error in errors:
    print(error)

# Output:
# Field 'ssn' (***6789): Value must match SSN format
# Field 'status' (INVALID): Value must be one of: ACTIVE, CLOSED
```

Notice:
- SSN value is masked as `***6789` (last 4 chars visible)
- Non-PII fields (status) show full value

---

## Masking Strategy

| Scenario | Original Value | Masked Value |
|----------|---------------|--------------|
| Length > 4 | `123-45-6789` | `***6789` |
| Length ≤ 4 | `1234` | `***` |
| Empty/None | `""` | `""` |

---

## How to Configure PII Fields

### In Schema Definition
```python
SchemaField(
    name="field_name",
    field_type="STRING",
    is_pii=True  # Mark as PII - masking enabled
)
```

### Common PII Fields
```python
fields=[
    # Personal identifiers
    SchemaField(name="ssn", field_type="STRING", is_pii=True),
    SchemaField(name="national_id", field_type="STRING", is_pii=True),
    SchemaField(name="passport_number", field_type="STRING", is_pii=True),
    
    # Contact information
    SchemaField(name="email", field_type="STRING", is_pii=True),
    SchemaField(name="phone", field_type="STRING", is_pii=True),
    SchemaField(name="mobile", field_type="STRING", is_pii=True),
    
    # Financial
    SchemaField(name="account_number", field_type="STRING", is_pii=True),
    SchemaField(name="credit_card", field_type="STRING", is_pii=True),
    
    # Non-PII (no masking)
    SchemaField(name="customer_id", field_type="STRING"),  # is_pii defaults to False
    SchemaField(name="status", field_type="STRING"),
]
```

---

## Implementation Details

### File: `validators/schema_validator.py`

```python
def _mask_pii(self, field_name: str, value: Any) -> str:
    """Mask PII fields in error output."""
    field = self._field_map.get(field_name)
    if field and field.is_pii and value:
        str_val = str(value)
        if len(str_val) > 4:
            return "***" + str_val[-4:]
        return "***"
    return str(value) if value is not None else ""
```

---

## No Separate Transform Needed

Originally, a separate `MaskPIIDoFn` Beam transform was proposed. However, this was **not implemented** because:

1. **Error messages already masked** - SchemaValidator handles PII masking in error output
2. **Data stored as-is** - Actual PII values are stored in BigQuery (with appropriate access controls)
3. **Simpler architecture** - No additional pipeline step needed

If a use case arises for masking PII values *in the data itself* before storage, a `MaskPIIDoFn` can be added later.

---

## Test Results

PII masking is tested as part of SchemaValidator tests:

```
tests/unit/validators/test_schema_validator.py::test_pii_field_masked_in_errors ✅
tests/unit/validators/test_schema_validator.py::test_pii_masking_short_value ✅
tests/unit/validators/test_schema_validator.py::test_non_pii_not_masked ✅
```

---

## Summary

| Aspect | Implementation |
|--------|----------------|
| Configuration | `is_pii=True` on SchemaField |
| Where Applied | Error messages during validation |
| Masking Strategy | Last 4 chars visible with `***` prefix |
| Separate Transform | Not needed |
| Data in BigQuery | Unmasked (rely on IAM for access control) |
