# 📊 LOA Blueprint - Complete Data Quality Framework Guide

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quality Scoring](#quality-scoring)
3. [Quality Checks](#quality-checks)
4. [Anomaly Detection](#anomaly-detection)
5. [Malformed Data Handling](#malformed-data-handling)
6. [Audit & Reconciliation](#audit--reconciliation)
7. [Implementation Guide](#implementation-guide)
8. [Team Guidelines](#team-guidelines)

---

## 🎯 Overview

The LOA Blueprint provides a complete data quality framework with:
- **Quality Scoring** - Numerical assessment of data quality
- **Quality Checks** - Automated validation of completeness, uniqueness, validity
- **Anomaly Detection** - Statistical detection of outliers and anomalies
- **Malformed Data Handling** - Safe quarantine and deletion procedures
- **Audit Trail** - Complete history of all data changes
- **Reconciliation** - Source-to-target verification

### Goals
✅ Detect quality issues early  
✅ Prevent bad data from reaching BigQuery  
✅ Enable safe data recovery  
✅ Maintain complete audit trail  
✅ Support compliance requirements  

---

## 📊 Quality Scoring

### What is Quality Score?

A numerical score (0-100) representing overall data quality:
- **90-100:** Excellent - Production ready
- **80-89:** Good - Acceptable with minor issues
- **70-79:** Fair - Requires review
- **Below 70:** Poor - Fix required before load

### How Scores Are Calculated

**Quality Score = Average of:**
1. Completeness Score (30% weight)
   - Percentage of non-null required fields
   - Target: 100%

2. Uniqueness Score (25% weight)
   - Percentage of unique IDs
   - Target: 100%

3. Validity Score (25% weight)
   - Percentage of records passing validation rules
   - Target: 100%

4. Timeliness Score (20% weight)
   - Percentage of recent data
   - Target: 100% within SLA

### Example Calculation

```
Completeness: 95% → 95 points
Uniqueness: 98% → 98 points
Validity: 90% → 90 points
Timeliness: 100% → 100 points

Quality Score = (95×0.30 + 98×0.25 + 90×0.25 + 100×0.20) / 1.0
             = (28.5 + 24.5 + 22.5 + 20.0)
             = 95.5 (Excellent! ✅)
```

---

## ✅ Quality Checks

### 1. Completeness Check

**What:** Ensures required fields are present and non-null

**How:**
```python
from gdw_data_core.core.data_quality import DataQualityChecker

checker = DataQualityChecker()
# ... logic using the checker ...
```

**Target:** 100% (all required fields present)

### 2. Uniqueness Check

**What:** Ensures no duplicate key values

**How:**
```python
uniqueness = checker.check_uniqueness(
    data=[
        {"id": "APP001", "name": "John"},
        {"id": "APP002", "name": "Jane"},
        {"id": "APP001", "name": "John"}  # Duplicate!
    ],
    key_field="id"
)
# Result: 2/3 = 0.667 (66.7%)
```

**Target:** 100% (no duplicates)

### 3. Validity Check

**What:** Ensures data matches expected format/rules

**How:**
```python
def validate_ssn(ssn):
    return len(ssn) == 11 and ssn.count("-") == 2

validity = checker.check_validity(
    data=[
        {"ssn": "123-45-6789"},
        {"ssn": "INVALID"},  # Bad format!
        {"ssn": "345-67-8901"}
    ],
    field="ssn",
    validation_fn=validate_ssn
)
# Result: 2/3 = 0.667 (66.7%)
```

**Target:** 100% (all records valid)

### 4. Consistency Check

**What:** Ensures values in a field are consistent/expected

**How:**
```python
consistency = checker.check_consistency(
    data=[
        {"status": "ACTIVE"},
        {"status": "ACTIVE"},
        {"status": "ACTIVE"},
        {"status": "INACTIVE"}  # Outlier
    ],
    field="status"
)
# Result: High consistency (75%+ same value)
```

**Target:** 95%+ (values consistent with expectations)

### 5. Timeliness Check

**What:** Ensures data is current and not stale

**How:**
```python
from datetime import datetime, timedelta

timeliness = checker.check_timeliness(
    data=[
        {"timestamp": datetime.utcnow()},
        {"timestamp": datetime.utcnow() - timedelta(hours=1)},
        {"timestamp": datetime.utcnow() - timedelta(days=5)}  # Stale!
    ],
    field="timestamp",
    max_age_hours=24
)
# Result: 2/3 = 0.667 (66.7% recent)
```

**Target:** 100% (data within 24 hours)

---

## 🔍 Anomaly Detection

### Statistical Outliers

**Purpose:** Find unusual values that might indicate errors

**Example:**
```python
from gdw_data_core.core.data_quality import AnomalyDetector

detector = AnomalyDetector()

# Normal amounts: 100K-500K
# Outlier: 5M
amounts = [100000, 150000, 200000, 250000, 5000000]

outliers = detector.detect_statistical_outliers(
    amounts,
    threshold_std=3  # 3 standard deviations
)
# Result: [5000000] is outlier
```

### Pattern Anomalies

**Purpose:** Detect when data breaks expected patterns

**Example:**
```python
# Expected pattern: APP001, APP002, APP003...
# Anomaly: APP999 (breaks sequence)

ids = ["APP001", "APP002", "APP999", "APP003"]

# Would detect APP999 as anomalous
pattern_check = detector.detect_pattern_anomaly(ids)
```

### Missing Value Anomalies

**Purpose:** Detect unusual rates of missing data

**Example:**
```python
# Normal: 1-5% missing
# Anomalous: 60% missing!

data = [
    {"ssn": "123-45-6789"},
    {"ssn": None},
    {"ssn": None},
    {"ssn": None},
    {"ssn": "345-67-8901"}
]

# Would detect 60% missing rate as anomalous
missing_check = detector.detect_missing_value_anomaly(data)
```

---

## 🛑 Malformed Data Handling

### Detection

Malformed data = Any record that fails quality checks

```python
from gdw_data_core.core.data_deletion import DataDeletionFramework

framework = DataDeletionFramework(
    pipeline_name="loa_pipeline",
    run_id="run_20251221_120000"
)

# Detect malformed record
malformed = framework.detect_malformed_record(
    record_id="APP001",
    entity_type="APPLICATION",
    data={"id": "APP001", "ssn": None, "amount": "INVALID"},
    validation_errors=["Missing SSN", "Invalid amount format"],
    severity="HIGH"
)
```

### Quarantine

Malformed records are quarantined before deletion:

```python
# Mark for quarantine
framework.quarantine_malformed(malformed)

# Records moved to quarantine bucket in GCS
# gs://quarantine-bucket/malformed/2025-12-21/APP001.json
```

### Approval Workflow

```
Detect → Quarantine → Request Approval → Delete (if approved) → Audit Trail
```

### Safe Deletion with Recovery

```python
# 1. Create recovery point BEFORE deletion
framework.create_recovery_point(
    checkpoint_name="before_deletion_batch_1",
    state={"records_count": 100, "timestamp": "2025-12-21T12:00:00"}
)

# 2. Request approval
approval_request = framework.request_deletion_approval(malformed)

# 3. Approve (after human review)
framework.approve_deletion(malformed, approved_by="data_steward@company.com")

# 4. Delete
framework.delete_record(malformed)

# 5. Can restore if needed
restored = framework.restore_from_recovery_point("before_deletion_batch_1")
```

---

## 📋 Audit & Reconciliation

### Audit Trail

Complete history of all data operations:

```python
from loa_common.audit import AuditTrail

audit_trail = AuditTrail(
    pipeline_name="loa_pipeline",
    run_id="run_20251221"
)

# Log every record processed
for record in records:
    if is_valid(record):
        audit_trail.log_entry(
            record_id=record["id"],
            entity_type="APPLICATION",
            status="LOADED"
        )
    else:
        audit_trail.log_entry(
            record_id=record["id"],
            entity_type="APPLICATION",
            status="FAILED",
            error_reason="Validation error"
        )

# Query audit trail
loaded_count = audit_trail.get_entry_count_by_status("LOADED")
failed_count = audit_trail.get_entry_count_by_status("FAILED")
```

### Reconciliation

Verify source data matches BigQuery:

```python
from loa_common.audit import ReconciliationEngine

reconciler = ReconciliationEngine()

# Source: 1000 records
# Target (BQ): 950 records
report = reconciler.reconcile(
    source_records=source_data,
    target_records=bq_data,
    key_field="id"
)

print(f"Source: {report.source_count}")  # 1000
print(f"Target: {report.target_count}")  # 950
print(f"Matched: {report.matched_count}")  # 950
print(f"Missing: {report.missing_count}")  # 50 (not in BQ)
print(f"Extra: {report.extra_count}")  # 0 (not in source)
```

---

## 🛠️ Implementation Guide

### For Data Engineers

#### Step 1: Load and Validate
```python
from loa_common.data_quality import DataQualityChecker

checker = DataQualityChecker()

# Load data
data = load_csv("gs://input/applications.csv")

# Check quality
completeness = checker.check_completeness(data, required_fields)
validity = checker.check_validity(data, "ssn", validate_ssn)
```

#### Step 2: Detect Issues
```python
from loa_common.data_deletion import DataDeletionFramework

framework = DataDeletionFramework(pipeline_name, run_id)

# Find malformed records
for record in data:
    errors = validate_record(record)
    if errors:
        framework.detect_malformed_record(
            record_id=record["id"],
            entity_type="APPLICATION",
            data=record,
            validation_errors=errors
        )
```

#### Step 3: Handle Malformed Data
```python
# Quarantine
for malformed in framework.malformed_records:
    framework.quarantine_malformed(malformed)

# Or if pre-approved for deletion
for malformed in framework.malformed_records:
    if malformed.severity == "CRITICAL":
        framework.approve_deletion(malformed, approved_by="system")
        framework.delete_record(malformed)
```

#### Step 4: Report Quality
```python
# Get quality score
report = DataQualityReport(
    data_source="applications.csv",
    timestamp=datetime.utcnow()
)

report.add_metric("completeness", completeness)
report.add_metric("validity", validity)

score = report.calculate_quality_score()
print(f"Quality Score: {score}")  # 95 = Excellent!

# Create report
write_quality_report(report)
```

### For Teams Migrating JCL Jobs

#### Copy These Patterns:
```python
# 1. Copy quality checking pattern
from loa_common.data_quality import DataQualityChecker
# Use as-is, no changes needed!

# 2. Copy validation patterns
from loa_common.validation import validate_ssn, validate_date
# Reuse these functions

# 3. Copy malformed data handling
from loa_common.data_deletion import DataDeletionFramework
# Use same quarantine/deletion approach

# 4. Copy audit trail pattern
from loa_common.audit import AuditTrail
# Log every record loaded/failed
```

---

## 📊 Quality Metrics Dashboard

### Key Metrics to Track

```
Pipeline Run Metrics:
├─ Completeness: 97%
├─ Uniqueness: 99%
├─ Validity: 95%
├─ Timeliness: 100%
├─ Quality Score: 97/100 ✅
├─ Records Processed: 10,000
├─ Records Loaded: 9,850
├─ Records Failed: 150
├─ Records Malformed: 12
└─ Audit Trail Entries: 10,000
```

### When to Alert

- Quality Score < 80
- Completeness < 95%
- Validity < 90%
- Malformed records > 1%
- Loading failures > 2%

---

## 🎓 Best Practices

### ✅ DO

- Check completeness before processing
- Detect anomalies early
- Quarantine before deleting
- Log all operations
- Create recovery points
- Reconcile with source
- Monitor quality scores
- Alert on issues
- Archive audit logs
- Document decisions

### ❌ DON'T

- Delete data without approval
- Ignore quality warnings
- Skip validation checks
- Process invalid data
- Delete without recovery point
- Assume data is clean
- Ignore anomalies
- Skip audit logging
- Delete audit trail early
- Process unreconciled data

---

## 📈 Success Metrics

**Target Quality Scores:**
- Applications: 95%+
- Customers: 95%+
- Branches: 98%+
- Collateral: 95%+

**Success Criteria:**
- Zero data loss (complete audit trail)
- 100% of malformed data detected
- < 1% invalid records loaded
- < 2% loading failures
- 100% reconciliation match

---

## 📚 References

### Related Documentation
- [Testing Strategy](./TESTING_STRATEGY.md)
- [Audit Integration Guide](./AUDIT_INTEGRATION_GUIDE.md)
- [Error Handling Guide](./ERROR_HANDLING_GUIDE.md)
- [GDW Data Core Documentation](../../gdw_data_core/README.md)
- [LOA Domain Validation](../../blueprint/components/loa_domain/validation.py)

### External Resources
- Data Quality Frameworks
- Great Expectations (Python library)
- dbt tests for DBT models
- DataHub for metadata

---

## 🎉 Summary

The LOA Blueprint provides:
- ✅ Automated quality scoring
- ✅ Complete quality checks
- ✅ Anomaly detection
- ✅ Safe malformed data handling
- ✅ Full audit trail
- ✅ Source-to-target reconciliation

**Teams can:**
1. Copy quality checking patterns
2. Use provided validation functions
3. Implement quarantine/deletion workflow
4. Maintain audit trail automatically
5. Reconcile with source data

**Result:** High-quality data with complete auditability!

---

**Last Updated:** December 21, 2025  
**Status:** Production Ready  
**Maintained By:** LOA Blueprint Team

For implementation help, see: `blueprint/docs/DATA_QUALITY_GUIDE.md`

