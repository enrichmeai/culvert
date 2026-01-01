# GDW Data Core - Transformations Module Implementation Prompt

**Ticket ID:** LIBRARY-TRANSFORM-001
**Status:** Ready for Implementation
**Component:** `gdw_data_core/transformations`

---

## 📋 OVERVIEW

The Transformations module provides reusable data transformation utilities for the legacy mainframe-to-GCP migration framework. This module covers two transformation paradigms:

1. **dbt Macros (SQL)** - For BigQuery transformations in the data warehouse layer
2. **Python Transforms** - For Apache Beam DoFn transforms in the pipeline layer

### Current State

```
gdw_data_core/transformations/
└── dbt_shared/
    └── macros/
        ├── audit_columns.sql      # Audit column macros
        ├── data_quality_check.sql # DQ check macros
        └── pii_masking.sql        # PII masking macros

gdw_data_core/pipelines/beam/transforms/
├── __init__.py
├── parsers.py           # ParseCsvLine
├── validators.py        # ValidateRecordDoFn
├── filters.py           # FilterRecordsDoFn
├── transformers.py      # TransformRecordDoFn
├── enrichers.py         # EnrichWithMetadataDoFn
└── deduplicators.py     # DeduplicateRecordsDoFn
```

---

## 🎯 OBJECTIVES

### Objective 1: Audit & Validate Existing dbt Macros

Review and validate the existing dbt macros for:
- Correctness (SQL syntax, BigQuery compatibility)
- Completeness (all documented features implemented)
- Consistency (naming conventions, parameter patterns)
- Error handling (graceful failures, proper logging)

### Objective 2: Audit & Validate Beam Transforms

Review and validate the existing Beam transforms for:
- Proper DoFn implementation patterns
- Metrics collection (counters, gauges)
- Error handling (tagged outputs for errors)
- Type hints and docstrings
- Unit test coverage

### Objective 3: Identify Missing Transformations

Based on mainframe migration requirements, identify missing:
- Field mapping transforms (EBCDIC → ASCII, packed decimal)
- Date format conversions (mainframe dates → ISO 8601)
- Code translation (mainframe codes → modern values)
- Record type routing (multi-record mainframe files)

---

## 📁 MODULE STRUCTURE REQUIREMENTS

### dbt Macros Structure

```
gdw_data_core/transformations/
├── __init__.py                    # Package marker
├── README.md                      # Transformations documentation
└── dbt_shared/
    ├── dbt_project.yml            # dbt project config (for testing)
    ├── macros/
    │   ├── _schema.yml            # Macro documentation
    │   ├── audit/
    │   │   ├── add_audit_columns.sql
    │   │   ├── apply_audit_columns.sql
    │   │   └── create_audit_trail.sql
    │   ├── data_quality/
    │   │   ├── check_completeness.sql
    │   │   ├── check_uniqueness.sql
    │   │   ├── check_value_range.sql
    │   │   ├── check_pattern_match.sql
    │   │   └── check_freshness.sql
    │   ├── pii/
    │   │   ├── mask_ssn.sql
    │   │   ├── mask_account.sql
    │   │   ├── mask_email.sql
    │   │   ├── mask_phone.sql
    │   │   └── create_masked_view.sql
    │   ├── incremental/
    │   │   ├── merge_strategy.sql
    │   │   ├── append_strategy.sql
    │   │   └── delete_insert_strategy.sql
    │   └── mainframe/
    │       ├── convert_packed_decimal.sql
    │       ├── convert_mainframe_date.sql
    │       └── translate_codes.sql
    └── tests/
        └── macro_tests.sql         # Macro unit tests
```

### Beam Transforms Structure (Already Correct)

The current structure follows the submodule pattern correctly:
```
gdw_data_core/pipelines/beam/transforms/
├── __init__.py          # Re-exports all DoFns
├── parsers.py           # ParseCsvLine
├── validators.py        # ValidateRecordDoFn
├── filters.py           # FilterRecordsDoFn
├── transformers.py      # TransformRecordDoFn
├── enrichers.py         # EnrichWithMetadataDoFn
└── deduplicators.py     # DeduplicateRecordsDoFn
```

---

## 🔍 AUDIT CHECKLIST

### dbt Macro Audit

For each macro file, verify:

#### 1. `audit_columns.sql`
- [ ] `add_audit_columns()` - Adds run_id, processed_timestamp, source_file
- [ ] `apply_audit_columns(relation)` - ALTER TABLE adds columns
- [ ] `create_audit_trail(source, dest)` - Creates audit snapshot
- [ ] Uses `var()` correctly for run_id, source_file
- [ ] BigQuery syntax correct (CURRENT_TIMESTAMP, STRING, etc.)

#### 2. `data_quality_check.sql`
- [ ] `check_required_fields(table, fields)` - NULL check
- [ ] `check_uniqueness(table, key)` - Duplicate detection
- [ ] `check_value_range(table, column, min, max)` - Range validation
- [ ] `check_pattern_match(table, column, pattern)` - Regex validation
- [ ] `check_freshness(table, column, max_hours)` - Staleness check
- [ ] Uses `exceptions.warn()` for threshold violations
- [ ] Configurable thresholds via `var()`

#### 3. `pii_masking.sql`
- [ ] `mask_ssn(column)` - Shows last 4 digits only
- [ ] `mask_ssn_full(column)` - Fully redacts
- [ ] `mask_account_number(column)` - Asterisks + last 4
- [ ] `mask_email(column)` - Shows domain only
- [ ] `mask_phone(column)` - Area code + last 4
- [ ] `mask_name(first, last)` - Initial + last name
- [ ] `mask_pii(column, type)` - Generic dispatcher
- [ ] `create_masked_view(source, view, rules)` - View generation

### Beam Transform Audit

For each transform file, verify:

#### 1. `parsers.py` - ParseCsvLine
- [ ] Handles CSV with headers
- [ ] Handles CSV without headers (positional)
- [ ] Handles quoted fields with commas
- [ ] Handles empty fields
- [ ] Metrics: `parse/success`, `parse/errors`
- [ ] Error output: `'errors'` tagged output
- [ ] Type hints on all methods
- [ ] Google-style docstring

#### 2. `validators.py` - ValidateRecordDoFn
- [ ] Accepts custom validation function
- [ ] Routes valid to main output
- [ ] Routes invalid to `'invalid'` output
- [ ] Captures validation errors in output
- [ ] Metrics: `validate/valid`, `validate/invalid`
- [ ] Type hints on all methods

#### 3. `filters.py` - FilterRecordsDoFn
- [ ] Accepts predicate function
- [ ] Yields records matching predicate
- [ ] Optionally yields filtered-out to `'filtered'`
- [ ] Metrics: `filter/passed`, `filter/dropped`

#### 4. `transformers.py` - TransformRecordDoFn
- [ ] Accepts transform function
- [ ] Returns transformed record
- [ ] Routes errors to `'errors'` output
- [ ] Metrics: `transform/success`, `transform/errors`

#### 5. `enrichers.py` - EnrichWithMetadataDoFn
- [ ] Adds `run_id` to record
- [ ] Adds `processed_timestamp` to record
- [ ] Adds `source_file` to record (configurable)
- [ ] Accepts custom metadata dict
- [ ] Metrics: `enrich/success`

#### 6. `deduplicators.py` - DeduplicateRecordsDoFn
- [ ] Deduplicates by specified key field(s)
- [ ] Routes duplicates to `'duplicates'` output
- [ ] Metrics: `dedup/unique`, `dedup/duplicates`
- [ ] Stateful or stateless option

---

## 🆕 MISSING TRANSFORMATIONS

### dbt Macros to Add

#### Mainframe-Specific Macros

```sql
-- convert_packed_decimal.sql
{% macro convert_packed_decimal(column, precision, scale) %}
    -- Converts COBOL packed decimal (COMP-3) to BigQuery NUMERIC
    SAFE_CAST({{ column }} AS NUMERIC) / POWER(10, {{ scale }})
{% endmacro %}

-- convert_mainframe_date.sql
{% macro convert_mainframe_date(column, format) %}
    -- Formats: YYYYMMDD, YYMMDD, YYDDD (Julian), CYYMMDD (century)
    CASE
        WHEN '{{ format }}' = 'YYYYMMDD' THEN
            PARSE_DATE('%Y%m%d', {{ column }})
        WHEN '{{ format }}' = 'YYMMDD' THEN
            PARSE_DATE('%y%m%d', {{ column }})
        WHEN '{{ format }}' = 'YYDDD' THEN
            -- Julian date: 2-digit year + 3-digit day of year
            DATE_ADD(
                DATE(CONCAT('20', SUBSTR({{ column }}, 1, 2), '-01-01')),
                INTERVAL CAST(SUBSTR({{ column }}, 3, 3) AS INT64) - 1 DAY
            )
        WHEN '{{ format }}' = 'CYYMMDD' THEN
            -- Century format: C=0 for 1900s, C=1 for 2000s
            PARSE_DATE('%Y%m%d',
                CONCAT(
                    CASE WHEN SUBSTR({{ column }}, 1, 1) = '0' THEN '19' ELSE '20' END,
                    SUBSTR({{ column }}, 2)
                )
            )
        ELSE NULL
    END
{% endmacro %}

-- translate_codes.sql
{% macro translate_code(column, code_table, default_value) %}
    COALESCE(
        (SELECT description FROM {{ code_table }} WHERE code = {{ column }}),
        '{{ default_value }}'
    )
{% endmacro %}
```

#### Incremental Strategy Macros

```sql
-- watermark_incremental.sql
{% macro get_watermark(table, column) %}
    SELECT COALESCE(MAX({{ column }}), '1900-01-01') FROM {{ table }}
{% endmacro %}

{% macro filter_incremental(source, timestamp_col, watermark) %}
    SELECT * FROM {{ source }}
    WHERE {{ timestamp_col }} > '{{ watermark }}'
{% endmacro %}
```

### Beam Transforms to Add

#### Mainframe-Specific Transforms

```python
# gdw_data_core/pipelines/beam/transforms/mainframe.py

class ConvertPackedDecimalDoFn(beam.DoFn):
    """Convert COBOL packed decimal fields to Python Decimal."""

    def __init__(self, field_specs: Dict[str, Tuple[int, int]]):
        """
        Args:
            field_specs: Dict mapping field names to (precision, scale) tuples
        """
        self.field_specs = field_specs

class ConvertMainframeDateDoFn(beam.DoFn):
    """Convert mainframe date formats to ISO 8601."""

    def __init__(self, field_formats: Dict[str, str]):
        """
        Args:
            field_formats: Dict mapping field names to format codes
                          ('YYYYMMDD', 'YYMMDD', 'YYDDD', 'CYYMMDD')
        """
        self.field_formats = field_formats

class TranslateCodesDoFn(beam.DoFn):
    """Translate mainframe codes to modern values using lookup tables."""

    def __init__(self, code_mappings: Dict[str, Dict[str, str]]):
        """
        Args:
            code_mappings: Dict mapping field names to code translation dicts
        """
        self.code_mappings = code_mappings

class RouteByRecordTypeDoFn(beam.DoFn):
    """Route records to different outputs based on record type indicator."""

    def __init__(self, type_field: str, type_mapping: Dict[str, str]):
        """
        Args:
            type_field: Field containing record type code
            type_mapping: Dict mapping type codes to output tag names
        """
        self.type_field = type_field
        self.type_mapping = type_mapping
```

---

## ✅ IMPLEMENTATION TASKS

### Phase 1: Audit Existing (1-2 hours)

1. Review each dbt macro for correctness
2. Review each Beam transform for patterns
3. Document any issues found
4. Create unit tests for untested components

### Phase 2: Refactor dbt Structure (1 hour)

1. Split large macro files into subfolders
2. Create `_schema.yml` for documentation
3. Add macro tests
4. Update `dbt_project.yml`

### Phase 3: Add Missing Transforms (2-3 hours)

1. Add mainframe-specific dbt macros
2. Add mainframe-specific Beam transforms
3. Add unit tests for new components
4. Update `__init__.py` exports

### Phase 4: Documentation (1 hour)

1. Create `transformations/README.md`
2. Update main library README
3. Add usage examples
4. Document macro parameters

---

## 🧪 TESTING REQUIREMENTS

### dbt Macro Tests

```sql
-- tests/macro_tests.sql
{% macro test_add_audit_columns() %}
    SELECT
        '{{ add_audit_columns() }}' IS NOT NULL as test_result
{% endmacro %}

{% macro test_mask_ssn() %}
    SELECT
        {{ mask_ssn("'123-45-6789'") }} = '123-45-6789' as test_result
{% endmacro %}
```

### Beam Transform Tests

```python
# tests/unit/pipelines/beam/transforms/test_transformers.py

class TestTransformRecordDoFn(unittest.TestCase):

    def test_successful_transformation(self):
        transform_fn = lambda r: {**r, 'doubled': r['value'] * 2}
        dofn = TransformRecordDoFn(transform_fn)

        result = list(dofn.process({'value': 5}))

        self.assertEqual(result[0], {'value': 5, 'doubled': 10})

    def test_error_handling(self):
        transform_fn = lambda r: r['missing_key']  # Will raise KeyError
        dofn = TransformRecordDoFn(transform_fn)

        result = list(dofn.process({'value': 5}))

        # Should yield tagged error output
        self.assertIsInstance(result[0], beam.pvalue.TaggedOutput)
```

---

## 📊 SUCCESS CRITERIA

- [ ] All dbt macros pass syntax validation
- [ ] All dbt macros have documented parameters
- [ ] All Beam transforms have >80% test coverage
- [ ] All Beam transforms follow DoFn patterns
- [ ] All components have type hints
- [ ] All components have Google-style docstrings
- [ ] README documentation complete
- [ ] No duplicate code between library and blueprint

---

## 📎 REFERENCE

### Existing Patterns to Follow

**dbt Macro Pattern:**
```sql
-- Header comment with purpose
-- Usage example
-- Parameter documentation

{% macro macro_name(param1, param2) %}
    -- Implementation
    {{ result }}
{% endmacro %}
```

**Beam DoFn Pattern:**
```python
class MyDoFn(beam.DoFn):
    """One-line description.

    Detailed description of what the transform does.

    Attributes:
        attr1: Description

    Outputs:
        Main: Description of main output
        'tag': Description of tagged output

    Metrics:
        namespace/counter: Description

    Example:
        >>> dofn = MyDoFn(param)
        >>> result = list(dofn.process(element))
    """

    def __init__(self, param: Type):
        super().__init__()
        self.param = param
        self.success = beam.metrics.Metrics.counter("namespace", "success")
        self.errors = beam.metrics.Metrics.counter("namespace", "errors")

    def process(self, element: InputType) -> Iterator[OutputType]:
        try:
            result = transform(element)
            self.success.inc()
            yield result
        except Exception as e:
            self.errors.inc()
            yield beam.pvalue.TaggedOutput('errors', {'error': str(e), 'record': element})
```

---

**Ready for implementation. Start with Phase 1: Audit Existing.**


