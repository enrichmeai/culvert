# 🚀 LOA LOCAL DEPLOYMENT & TESTING GUIDE
## Understand the System Before Cloud Deployment

**For**: Lead Engineer, Lead Software Engineer  
**Status**: Ready to test locally first  
**Cost**: $0 (all local, no cloud resources)  
**Time**: 30 minutes to understand

---

## 🎯 WHAT YOU'LL LEARN

✅ How validation works  
✅ What valid vs invalid records look like  
✅ How error handling works  
✅ How metadata is captured  
✅ How the pipeline scales  
✅ Then → deploy to GCP with confidence  

---

## 📂 LOCAL DEPLOYMENT WALKTHROUGH

### Phase 1: Understanding the Code Structure (10 minutes)

**The LOA Blueprint has 3 core modules:**

```
loa_common/
├── validation.py      → Field validators (SSN, amount, type, etc.)
├── schema.py          → BigQuery schema definitions
└── io_utils.py        → GCS/Pub/Sub helpers

What they do:
├─ validation.py: Checks each field and returns errors
├─ schema.py: Defines how data looks in BigQuery
└─ io_utils.py: Handles cloud storage operations
```

### Phase 2: Run Local Test (5 minutes)

```bash
# Navigate to project
cd /path/to/project

# Run the test (shows 5 sample records being validated)
python3 test_loa_local.py

# Expected output:
# ✅ 2 records PASS validation
# ❌ 3 records FAIL with clear error messages
```

**What you'll see:**

```
SAMPLE DATA:
  APP001: Valid record → ✅ PASSES
  APP002: Valid record → ✅ PASSES
  APP003: Bad SSN → ❌ FAILS (SSN error)
  APP004: Negative amount → ❌ FAILS (amount error)
  APP005: Bad loan type → ❌ FAILS (type error)

RESULTS:
  ✅ Valid: 2 records (40%)
  ❌ Errors: 3 records (60%)
  📊 Total: 5 records processed
```

### Phase 3: Understand the Validation (5 minutes)

**Each field is validated:**

| Field | Rules |
|-------|-------|
| **SSN** | Must be XXX-XX-XXXX format, not all zeros, valid area code |
| **Loan Amount** | Must be numeric, >= $1, <= $1,000,000 |
| **Loan Type** | Must be MORTGAGE, PERSONAL, AUTO, or HOME_EQUITY |
| **App Date** | Must be YYYY-MM-DD, not future, not >5 years old |
| **Branch** | Must be 6-8 chars, format: 2 letters + 4 digits (e.g., NY1234) |

### Phase 4: Understand the Output (5 minutes)

**Valid records go to one table:**
```
BigQuery table: applications_raw
├─ APP001 ✅
├─ APP002 ✅
└─ All other valid records
```

**Invalid records go to error table:**
```
BigQuery table: applications_errors
├─ APP003 (error: SSN invalid)
├─ APP004 (error: Loan amount negative)
└─ APP005 (error: Loan type invalid)
```

**Each record also gets metadata:**
```
run_id: applications_20250119_143022_a1b2c3d4
processed_timestamp: 2025-01-19 14:30:22
source_file: loa_sample_data.csv
```

---

## 📖 REVIEW THE CODE

### 1. Validation Module (15 minutes to read)

**File**: `loa_common/validation.py` (150 lines)

**What it does:**
- `validate_ssn()` → Checks SSN format and rules
- `validate_loan_amount()` → Checks amount is numeric and in range
- `validate_loan_type()` → Checks against allowed types
- `validate_application_date()` → Checks format and logic
- `validate_branch_code()` → Checks format
- `validate_application_record()` → Runs all validators together

**Key feature: PII Masking**
```python
# In error messages, SSN is masked:
# Full:  123-45-6789
# Shown: ***-**-6789

# Reason: Never log full PII in error messages
```

**Example validation:**
```python
# Valid
validate_application_record({
    "ssn": "123-45-6789",           # ✅ Valid format
    "loan_amount": "50000",         # ✅ Within range
    "loan_type": "MORTGAGE",        # ✅ Allowed type
    "application_date": "2025-01-15" # ✅ Recent date
})
# Returns: (record, [])  # No errors

# Invalid
validate_application_record({
    "ssn": "000-00-0000",           # ❌ All zeros
    "loan_amount": "-5000",         # ❌ Negative
    "loan_type": "INVALID_TYPE",    # ❌ Not allowed
})
# Returns: (record, [3 ValidationError objects])
```

### 2. Schema Module (10 minutes to read)

**File**: `loa_common/schema.py` (100 lines)

**What it defines:**
```python
APPLICATIONS_RAW_SCHEMA = [
    # Raw table (as received)
    {"name": "application_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE"},
    {"name": "loan_amount", "type": "INTEGER", "mode": "NULLABLE"},
    ...
]

APPLICATIONS_ERROR_SCHEMA = [
    # Error table (validation failures)
    {"name": "application_id", "type": "STRING"},
    {"name": "error_field", "type": "STRING"},
    {"name": "error_message", "type": "STRING"},
    ...
]
```

**Helper functions:**
```python
# Get field names
get_field_names(APPLICATIONS_RAW_SCHEMA)
# Returns: ["application_id", "ssn", "loan_amount", ...]

# Get required fields
get_required_fields(APPLICATIONS_RAW_SCHEMA)
# Returns: ["application_id"]

# Convert record for BigQuery
record_to_bq_compatible(record)
# Handles: type conversions, formatting, etc.
```

### 3. I/O Utilities Module (5 minutes to read)

**File**: `loa_common/io_utils.py` (70 lines)

**What it provides:**
```python
# Cloud Storage operations
GCSClient.list_files("bucket", "prefix/")
GCSClient.read_file("bucket", "path/to/file.csv")
GCSClient.write_file("bucket", "path/to/file.csv", content)
GCSClient.archive_file("bucket", "source", "archive/")

# Messaging operations
PubSubClient.publish_event("topic", {"status": "complete"})

# Tracking utilities
generate_run_id("applications")
# Returns: "applications_20250119_143022_a1b2c3d4"

discover_split_files("bucket", "app_20250119_")
# Returns: ["app_20250119_1.csv", "app_20250119_2.csv", ...]
```

---

## 🏗️ HOW THE PIPELINE WORKS

### Complete Data Flow

```
Step 1: Source Data
  ├─ Mainframe/Teradata CSV files
  ├─ Uploaded to GCS bucket
  └─ Example: gs://bucket/raw/applications_20250119.csv

Step 2: Read Files
  ├─ Dataflow reads from GCS
  ├─ Splits into records
  └─ Example: 1000 application records

Step 3: Parse & Validate
  ├─ Each record goes through validators
  ├─ Validation module checks ALL fields
  └─ Result: Valid or errors

Step 4: Route Records
  ├─ Valid records → applications_raw table
  ├─ Invalid records → applications_errors table
  └─ All records → Labeled with metadata

Step 5: BigQuery Storage
  ├─ applications_raw: 750 valid records ✅
  ├─ applications_errors: 250 error records ❌
  └─ Total: 1000 records processed (100%)

Step 6: Notification
  ├─ Send completion event to Pub/Sub
  ├─ Triggers downstream processing
  └─ Archive source file
```

### Processing Logic

```
Input: Raw CSV Record
{
    "application_id": "APP001",
    "ssn": "123-45-6789",
    "loan_amount": "50000",
    "loan_type": "MORTGAGE",
    "application_date": "2025-01-15",
    "branch_code": "NY1234"
}
    ↓
    Validation Module
    ├─ SSN format? ✅
    ├─ Amount range? ✅
    ├─ Loan type valid? ✅
    ├─ Date logic? ✅
    └─ Branch format? ✅
    ↓
Output: Valid Record
{
    "run_id": "app_20250119_143022_a1b2c3d4",
    "processed_timestamp": "2025-01-19 14:30:22",
    "source_file": "applications_20250119.csv",
    "application_id": "APP001",
    "ssn": "123-45-6789",
    "loan_amount": 50000,  # Converted to int
    "loan_type": "MORTGAGE",
    "application_date": "2025-01-15",
    "branch_code": "NY1234"
}
    ↓
    BigQuery: applications_raw table
```

---

## 🔄 LOCAL TEST WALKTHROUGH

### Run the Test

```bash
cd /path/to/project
python3 test_loa_local.py
```

### What Happens

```
1. Creates 5 sample records (2 good, 3 bad)
2. Shows sample data table
3. Explains validation rules
4. Shows validation results:
   ✅ APP001: VALID
   ✅ APP002: VALID
   ❌ APP003: SSN error
   ❌ APP004: Amount error
   ❌ APP005: Type error
5. Displays BigQuery schema
6. Shows data flow diagram
7. Displays metrics
8. Explains next steps
```

### Expected Output

```
======================================================================
              LOA BLUEPRINT - LOCAL TEST & DEPLOYMENT
======================================================================

📊 STEP 1: SAMPLE DATA
────────────────────────────────────────────────────────────────────
ID       SSN            Name            Amount    Type        Date
────────────────────────────────────────────────────────────────────
APP001   ***-**-6789    John Doe           $50000  MORTGAGE
APP002   ***-**-7890    Jane Smith         $30000  PERSONAL
APP003   ***-**-0000    Bad SSN            $25000  MORTGAGE  ❌
APP004   ***-**-8901    Bob                 -$5000  MORTGAGE  ❌
APP005   ***-**-9012    Alice              $75000  INVALID   ❌

⚙️ STEP 3: VALIDATION RESULTS
────────────────────────────────────────────────────────────────────

✅ VALID APP001
  → Ready for BigQuery

✅ VALID APP002
  → Ready for BigQuery

❌ FAILED APP003
  ❌ SSN: Cannot be all zeros or same digit

❌ FAILED APP004
  ❌ Loan Amount: Must be >= $1

❌ FAILED APP005
  ❌ Loan Type: Must be one of: MORTGAGE, PERSONAL, AUTO, HOME_EQUITY

======================================================================
📊 SUMMARY
======================================================================
Total records processed: 5
✅ Valid records: 2 (40%)
❌ Error records: 3 (60%)
```

---

## 💡 KEY CONCEPTS TO UNDERSTAND

### 1. Validation Pattern
```python
validated, errors = validate_application_record(record)

if errors:
    # Write to error table
    insert_to_bigquery(applications_errors, record, errors)
else:
    # Write to success table
    insert_to_bigquery(applications_raw, validated)
```

### 2. PII Masking
```python
# Never log full sensitive data
# Example:
ssn = "123-45-6789"
masked = f"***-**-{ssn[-4:]}"  # *** -**-6789

# Why: Protects customer privacy
```

### 3. Metadata Enrichment
```python
# Every record gets tracked
record["run_id"] = generate_run_id("applications")
record["processed_timestamp"] = datetime.now()
record["source_file"] = filename
```

### 4. Error Isolation
```python
# Good: Separate error table
applications_raw ← Valid records only
applications_errors ← Problematic records

# Benefit: Easy to find and fix issues
```

### 5. Scalability Pattern
```python
# Process 100 records → Same code
# Process 1M records → Same code (just more time)
# Scales because: Each record independent
```

---

## 🎓 WHAT YOU'LL UNDERSTAND BY NOW

After running the local test and reading the code, you'll know:

✅ **How validation works**
  - Field-level rules
  - Error objects
  - PII masking

✅ **What happens to records**
  - Valid → applications_raw
  - Invalid → applications_errors
  - All → Get metadata

✅ **How to extend it**
  - Add new validators (function)
  - Add new fields (schema)
  - Add new rules (regex, range checks)

✅ **Why it scales**
  - Stateless processing
  - Parallel capable
  - Cost-effective

✅ **How to debug it**
  - Look at error table
  - Read error messages
  - Trace through code

---

## 🚀 NEXT: DEPLOY TO GCP

Once you understand the local test:

1. **Follow HANDS_ON_IMPLEMENTATION_GUIDE.md**
   - Part 3: GCP Setup
   - Part 4: BigQuery Tables
   - Part 5: Actual Deployment

2. **Create GCP Resources**
   - Project
   - APIs
   - Buckets
   - Tables

3. **Upload Real Data**
   - Use same code
   - Process real records
   - See results in BigQuery

4. **Monitor & Optimize**
   - Track costs ($0-20 for testing)
   - Check quality metrics
   - Optimize queries

---

## 📋 LOCAL TEST CHECKLIST

- [ ] Navigate to project directory
- [ ] Run `python3 test_loa_local.py`
- [ ] See all 5 records processed
- [ ] Understand validation results
- [ ] Review the schema
- [ ] Read the data flow
- [ ] Understand the metrics
- [ ] Ready to go to GCP!

---

## 🎉 OUTCOME

You'll have:
✅ Deep understanding of validation logic  
✅ Clear picture of data flow  
✅ Confidence to deploy to GCP  
✅ Knowledge of how to scale  
✅ Ability to debug issues  

**All in 30 minutes, $0 cost, no cloud resources needed!**

---

**Next Step**: Read `HANDS_ON_IMPLEMENTATION_GUIDE.md` Part 3 for GCP deployment!

