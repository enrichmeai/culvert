# LOA BLUEPRINT - VISUAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOA MAINFRAME → GCP MIGRATION                        │
│                          (Blueprint Overview)                           │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│   MAINFRAME     │         │   LANDING ZONE   │         │  PROCESSING  │
│   (Legacy)      │  ───→   │   (GCS Bucket)   │  ───→   │  (Dataflow)  │
└─────────────────┘         └──────────────────┘         └──────────────┘
                                                                  │
      JCL Jobs:                Files Pattern:                    │
   ┌──────────┐             ┌────────────────┐                  │
   │ APPLOA01 │             │ applications_  │                  │
   │ APPLOA02 │      →      │   20250115_1   │        ┌─────────┴────────┐
   │ APPLOA03 │             │   20250115_2   │        │   VALIDATION     │
   │ APPLOA04 │             │   20250115_3   │        │  (loa_common)    │
   └──────────┘             └────────────────┘        └─────────┬────────┘
                                                                 │
    Split Files:                Triggered by:           ┌───────┴───────┐
  - Large datasets           Cloud Composer DAG         │               │
  - 1GB+ per file            (Airflow)                 ▼               ▼
  - Parallel load                                   VALID           ERRORS
                                                   RECORDS         RECORDS
                                                      │               │
                             ┌────────────────────────┘               │
                             │                                        │
                             ▼                                        ▼
                     ┌───────────────┐                     ┌──────────────────┐
                     │   BigQuery    │                     │    BigQuery      │
                     │ applications_ │                     │  applications_   │
                     │     raw       │                     │     errors       │
                     └───────────────┘                     └──────────────────┘


═══════════════════════════════════════════════════════════════════════════
                         LOA BLUEPRINT COMPONENTS
═══════════════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────────┐
│  1. SHARED LIBRARY (loa_common/)                                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  validation.py                 Schema-driven field validation        │
│  ├─ validate_ssn()            → SSN format, area codes, patterns     │
│  ├─ validate_loan_amount()    → Range $1 to $1M, numeric check       │
│  ├─ validate_loan_type()      → MORTGAGE, PERSONAL, AUTO, etc.       │
│  ├─ validate_application_date() → Date format, range checks          │
│  ├─ validate_branch_code()    → Alphanumeric format validation       │
│  └─ validate_application_record() → Orchestrates all validations     │
│                                                                       │
│  schema.py                     BigQuery table definitions            │
│  ├─ APPLICATIONS_RAW_SCHEMA   → Valid records + metadata             │
│  ├─ APPLICATIONS_ERROR_SCHEMA → Error records + diagnostics          │
│  └─ APPLICATIONS_PROCESSED_SCHEMA → Post-processing enrichment       │
│                                                                       │
│  io_utils.py                   GCS and Pub/Sub helpers               │
│  ├─ list_gcs_files()          → Find split files with wildcards      │
│  ├─ archive_files()           → Move to archive/ after processing    │
│  └─ publish_event()           → Pub/Sub notification on completion   │
└──────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│  2. PIPELINE TEMPLATES (loa_pipelines/)                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  loa_jcl_template.py          Apache Beam/Dataflow Pipeline          │
│  ├─ ParseCsv DoFn            → CSV line → dict conversion            │
│  ├─ ValidateRecord DoFn       → Apply loa_common.validation          │
│  ├─ EnrichMetadata DoFn       → Add run_id, timestamp, source        │
│  ├─ WriteToBigQuery           → Valid records → applications_raw     │
│  └─ WriteErrors               → Error records → applications_errors  │
│                                                                       │
│  dag_template.py              Cloud Composer/Airflow DAG Factory      │
│  ├─ GCSObjectExistenceSensor  → Wait for input files                 │
│  ├─ PythonOperator            → Discover split files                 │
│  ├─ DataflowTemplatedJobOp    → Run Beam pipeline                    │
│  ├─ BigQueryCheckOperator     → Validate row counts, quality         │
│  ├─ PythonOperator            → Archive processed files              │
│  └─ PythonOperator            → Send notification                    │
└──────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│  3. TESTING & VALIDATION (tests/, test_*.py)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  test_loa_local.py            Simple demo (no dependencies)          │
│  ├─ Sample data (5 records)  → 2 valid, 3 errors                     │
│  ├─ Mock validation           → Show validation rules                │
│  └─ Visual output             → Easy to understand results           │
│                                                                       │
│  test_validation_live.py      Test real validation functions         │
│  ├─ Import loa_common         → Test actual code                     │
│  ├─ Edge cases                → Invalid SSNs, negative amounts        │
│  └─ Full record validation    → End-to-end test                      │
│                                                                       │
│  tests/test_validation.py     Unit tests (pytest)                    │
│  └─ Comprehensive test suite  → All edge cases covered               │
└──────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                            DATA FLOW DIAGRAM
═══════════════════════════════════════════════════════════════════════════

MAINFRAME OUTPUT                 GCS LANDING ZONE
─────────────────               ──────────────────
                                                    
applications.dat      ───┐      applications_20250115_1.csv
(100MB, flat file)       │      applications_20250115_2.csv
                         ├────→ applications_20250115_3.csv
Split by JCL job         │      (30MB each)
or manually              │      
                    ─────┘      
                                         │
                                         │ Cloud Composer detects files
                                         │ Triggers Dataflow job
                                         ▼
                            ┌─────────────────────────┐
                            │  DATAFLOW PIPELINE      │
                            │  (Apache Beam)          │
                            └─────────────────────────┘
                                         │
                                         │
                        ┌────────────────┴─────────────────┐
                        │                                  │
                        │ For each CSV line:               │
                        │  1. Parse to dict                │
                        │  2. Validate fields              │
                        │  3. Check business rules         │
                        │  4. Add metadata                 │
                        │                                  │
                        └────────────┬─────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                    Valid Records         Error Records
                          │                     │
                          ▼                     ▼
             ┌─────────────────────┐  ┌──────────────────────┐
             │  BIGQUERY TABLE     │  │  BIGQUERY TABLE      │
             │  applications_raw   │  │  applications_errors │
             ├─────────────────────┤  ├──────────────────────┤
             │ • run_id            │  │ • run_id             │
             │ • timestamp         │  │ • timestamp          │
             │ • source_file       │  │ • source_file        │
             │ • application_id    │  │ • application_id     │
             │ • ssn               │  │ • error_field        │
             │ • applicant_name    │  │ • error_message      │
             │ • loan_amount       │  │ • error_value        │
             │ • loan_type         │  │ • raw_record (JSON)  │
             │ • application_date  │  │                      │
             │ • branch_code       │  │                      │
             └─────────────────────┘  └──────────────────────┘
                      │                          │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  DATA QUALITY       │
                      │  DASHBOARD          │
                      │                     │
                      │  • Success rate     │
                      │  • Error patterns   │
                      │  • Processing time  │
                      │  • Volume trends    │
                      └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                        VALIDATION FLOW (Detailed)
═══════════════════════════════════════════════════════════════════════════

RAW CSV LINE:
"APP001,123-45-6789,John Doe,50000,MORTGAGE,2025-01-15,NY1234"
     │
     ▼
PARSE TO DICT:
{
  "application_id": "APP001",
  "ssn": "123-45-6789",
  "applicant_name": "John Doe",
  "loan_amount": "50000",
  "loan_type": "MORTGAGE",
  "application_date": "2025-01-15",
  "branch_code": "NY1234"
}
     │
     ▼
VALIDATE EACH FIELD:
     │
     ├─→ validate_ssn("123-45-6789")
     │   ├─ Check format (XXX-XX-XXXX) ✓
     │   ├─ Check not 000-00-0000      ✓
     │   ├─ Check not 666-XX-XXXX      ✓
     │   ├─ Check area not 900-999     ✓
     │   └─ Return: []  (no errors)
     │
     ├─→ validate_loan_amount("50000")
     │   ├─ Check numeric              ✓
     │   ├─ Check >= $1                ✓
     │   ├─ Check <= $1,000,000        ✓
     │   └─ Return: 50000, []
     │
     ├─→ validate_loan_type("MORTGAGE")
     │   ├─ Check in allowed list      ✓
     │   └─ Return: []
     │
     ├─→ validate_application_date("2025-01-15")
     │   ├─ Check format YYYY-MM-DD    ✓
     │   ├─ Check not future           ✓
     │   ├─ Check not > 5 years old    ✓
     │   └─ Return: "2025-01-15", []
     │
     └─→ validate_branch_code("NY1234")
         ├─ Check alphanumeric         ✓
         ├─ Check length 6-8 chars     ✓
         └─ Return: []
     │
     ▼
ALL VALIDATIONS PASS
     │
     ▼
ENRICH WITH METADATA:
{
  "run_id": "20250119-123456-abc",
  "processed_timestamp": "2025-01-19T10:30:00Z",
  "source_file": "applications_20250115_1.csv",
  "application_id": "APP001",
  "ssn": "123-45-6789",
  "applicant_name": "John Doe",
  "loan_amount": 50000,
  "loan_type": "MORTGAGE",
  "application_date": "2025-01-15",
  "branch_code": "NY1234"
}
     │
     ▼
WRITE TO BIGQUERY
applications_raw table
✅ SUCCESS


IF VALIDATION FAILS:
═══════════════════
RAW CSV LINE:
"APP003,000-00-0000,Bad SSN,25000,MORTGAGE,2025-01-13,TX9012"
     │
     ▼
VALIDATE SSN("000-00-0000")
     │
     └─→ ValidationError:
         field: "ssn"
         value: "000-00-0000"
         message: "SSN cannot be all zeros or all same digit"
     │
     ▼
CREATE ERROR RECORD:
{
  "run_id": "20250119-123456-abc",
  "processed_timestamp": "2025-01-19T10:30:00Z",
  "source_file": "applications_20250115_1.csv",
  "application_id": "APP003",
  "error_field": "ssn",
  "error_message": "SSN cannot be all zeros or all same digit",
  "error_value": "***-**-0000",  ← PII masked!
  "raw_record": {original dict as JSON}
}
     │
     ▼
WRITE TO BIGQUERY
applications_errors table
❌ ERROR CAPTURED


═══════════════════════════════════════════════════════════════════════════
                      ORCHESTRATION FLOW (DAG)
═══════════════════════════════════════════════════════════════════════════

START (Daily at 2:00 AM)
     │
     ▼
┌─────────────────────────────┐
│ STEP 1: Wait for Files      │
│ (GCSObjectExistenceSensor)  │
│                             │
│ Check: gs://bucket/data/    │
│        applications_*.csv   │
└─────────────────────────────┘
     │ Files detected
     ▼
┌─────────────────────────────┐
│ STEP 2: Pre-Validation      │
│ (PythonOperator)            │
│                             │
│ Check:                      │
│  • File format & Headers    │
│  • Sampled Field-Level check│
│  • Discover split files     │
│  • BLOCK if invalid         │
└─────────────────────────────┘
     │ Format & Sample OK
     ▼
┌─────────────────────────────┐
│ STEP 3: Run Dataflow Job    │
│ (DataflowTemplatedJobOp)    │
│                             │
│ Process all split files:    │
│  • Intra-batch Deduplication│
│  • Full Field Validation    │
│  • Parallel processing      │
└─────────────────────────────┘
     │ Processing complete
     ▼
┌─────────────────────────────┐
│ STEP 4: Quality Checks      │
│ (BigQueryCheckOperator)     │
│                             │
│ Verify:                     │
│  • Row count > 0            │
│  • Global Deduplication     │
│  • Error rate < 10%         │
│  • Row count vs. Footer     │
└─────────────────────────────┘
     │ Quality checks pass
     ▼
┌─────────────────────────────┐
│ STEP 5: Archive Files       │
│ (PythonOperator)            │
│                             │
│ Move:                       │
│  from: data/                │
│  to:   archive/2025/01/19/  │
└─────────────────────────────┘
     │ Files archived
     ▼
┌─────────────────────────────┐
│ STEP 6: Send Notification   │
│ (PythonOperator)            │
│                             │
│ Publish to Pub/Sub:         │
│  • Records processed        │
│  • Error count              │
│  • Processing time          │
└─────────────────────────────┘
     │
     ▼
SUCCESS ✅


═══════════════════════════════════════════════════════════════════════════
                        KEY PATTERNS & PRINCIPLES
═══════════════════════════════════════════════════════════════════════════

1. SEPARATION OF CONCERNS
   ────────────────────────
   ✓ Validation logic ≠ Pipeline logic
   ✓ Schemas defined once, used everywhere
   ✓ I/O utilities reusable across projects
   ✓ Each module has single responsibility

2. ERROR ISOLATION
   ────────────────
   ✓ Errors don't stop processing
   ✓ Separate error table for diagnosis
   ✓ Full raw record preserved
   ✓ Clear error messages for data quality team

3. PII PROTECTION
   ───────────────
   ✓ SSN masked in logs: ***-**-6789
   ✓ SSN masked in error messages
   ✓ No sensitive data in plain text logs
   ✓ Compliant with data privacy requirements

4. METADATA ENRICHMENT
   ────────────────────
   ✓ run_id: Track each pipeline execution
   ✓ processed_timestamp: When record was processed
   ✓ source_file: Which file record came from
   ✓ Enables lineage and debugging

5. REUSABILITY
   ────────────
   ✓ Template pattern: One template → Many DAGs
   ✓ Same validation for batch and streaming
   ✓ Parameterized pipelines
   ✓ Copy-paste errors eliminated

6. TESTABILITY
   ────────────
   ✓ Local testing without GCP
   ✓ DirectRunner for integration tests
   ✓ Unit tests for each function
   ✓ Mock data for demonstrations


═══════════════════════════════════════════════════════════════════════════
                        SUCCESS METRICS
═══════════════════════════════════════════════════════════════════════════

DATA QUALITY METRICS:
   • Valid record rate: Target 95%+
   • Error patterns identified: All
   • PII protection: 100% compliant
   • Schema violations: 0

PERFORMANCE METRICS:
   • Processing time: <5 min for 1M records
   • Cost per record: <$0.001
   • Availability: 99.9%
   • Retry success rate: 99%

OPERATIONAL METRICS:
   • Failed runs: <1%
   • Mean time to recovery: <15 min
   • Data freshness: <30 min after file arrival
   • Manual intervention: <5% of runs


═══════════════════════════════════════════════════════════════════════════
                    WHAT MAKES THIS BLUEPRINT GOOD?
═══════════════════════════════════════════════════════════════════════════

✅ PRODUCTION-READY
   • Error handling at every step
   • Retry logic built-in
   • Monitoring hooks included
   • Logging comprehensive but PII-safe

✅ MAINTAINABLE
   • Clear code structure
   • Comprehensive docstrings
   • Type hints for IDE support
   • Consistent naming conventions

✅ SCALABLE
   • Handles 1K to 100M records
   • Auto-scaling with Dataflow
   • Parallel processing of split files
   • Cost-optimized (pay per use)

✅ EXTENSIBLE
   • Easy to add new validations
   • Template pattern for new JCL jobs
   • Pluggable I/O (GCS, S3, HDFS)
   • Support for streaming + batch

✅ COMPLIANT
   • PII protection built-in
   • Audit trail via metadata
   • Data lineage traceable
   • GDPR/privacy-ready


═══════════════════════════════════════════════════════════════════════════
```

