# LOA Migration Flow Diagrams

## Quick Reference: Legacy vs Modern Architecture

---

## 0. LOCAL TEST FLOW (test_loa_local.py) ⭐ YOU ARE HERE

```
┌───────────────────────────────────────────────────────────────────┐
│          WHAT test_loa_local.py EXECUTES                          │
│          (Local Validation Pattern Demo)                          │
└───────────────────────────────────────────────────────────────────┘

This script demonstrates the DATA VALIDATION FLOW (Section 4) 
running LOCALLY without any GCP services.

┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Generate Test Data                                    │
│  ─────────────────────────────────────────────────────────────  │
│  5 sample records (hardcoded in Python):                       │
│  • APP001: Valid record (SSN, amount, type, date all OK)      │
│  • APP002: Valid record                                        │
│  • APP003: Invalid SSN (000-00-0000)                           │
│  • APP004: Invalid amount (-5000)                              │
│  • APP005: Invalid loan type (INVALID_TYPE)                    │
│                                                                 │
│  📍 Maps to: Section 4 - "Input: Raw CSV Record"              │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Display Validation Rules                              │
│  ─────────────────────────────────────────────────────────────  │
│  Shows the business rules that would be in:                    │
│  • loa_common/validation.py (not executed, just documented)    │
│                                                                 │
│  Rules include:                                                 │
│  ✓ SSN format and validity                                     │
│  ✓ Loan amount range ($1 - $1M)                                │
│  ✓ Loan type (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)          │
│  ✓ Date format and range                                       │
│  ✓ Branch code format                                          │
│                                                                 │
│  📍 Maps to: Section 4 - "Step 2: Validate Each Field"        │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Mock Validation (Simulated)                           │
│  ─────────────────────────────────────────────────────────────  │
│  Instead of calling actual loa_common/validation.py,           │
│  this script SIMULATES the results:                            │
│                                                                 │
│  APP001 → ✅ VALID (no errors)                                 │
│  APP002 → ✅ VALID (no errors)                                 │
│  APP003 → ❌ FAILED (SSN error)                                │
│  APP004 → ❌ FAILED (Amount error)                             │
│  APP005 → ❌ FAILED (Loan type error)                          │
│                                                                 │
│  📍 Maps to: Section 4 - Validation splits to two paths       │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Show BigQuery Schema                                  │
│  ─────────────────────────────────────────────────────────────  │
│  Displays the target schema from loa_common/schema.py:         │
│  • 10 fields (run_id, timestamp, source_file, + data fields)  │
│  • Data types (STRING, INTEGER, DATE, TIMESTAMP)               │
│  • Descriptions                                                 │
│                                                                 │
│  This would be used in real pipeline to write to BigQuery      │
│                                                                 │
│  📍 Maps to: Section 4 - "BigQuery Raw Table"                 │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Visualize Data Flow                                   │
│  ─────────────────────────────────────────────────────────────  │
│  Shows ASCII diagram of how data flows:                        │
│  CSV → Validation → Split (valid/invalid) → BigQuery tables    │
│                                                                 │
│  📍 Maps to: Section 4 - Complete validation flow             │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: Display Metrics                                       │
│  ─────────────────────────────────────────────────────────────  │
│  Summary statistics:                                            │
│  • Total: 5 records                                             │
│  • Valid: 2 (40%)                                               │
│  • Errors: 3 (60%)                                              │
│  • Cost: $0 (local)                                             │
│                                                                 │
│  📍 Maps to: Section 7 - "Monitoring & Observability"         │
└─────────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  FINAL: Show Next Steps                                        │
│  ─────────────────────────────────────────────────────────────  │
│  Guides you to:                                                 │
│  1. Read actual validation code (loa_common/)                  │
│  2. Deploy to GCP                                               │
│  3. Scale up to production                                      │
│                                                                 │
│  📍 Maps to: Section 8 - "Migration Phases"                   │
└─────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                    KEY CHARACTERISTICS                            │
└───────────────────────────────────────────────────────────────────┘

✅ What it DOES:
   • Educational demo of validation pattern
   • Shows what errors look like
   • Demonstrates error isolation (separate tables)
   • PII masking example
   • Zero cost (no GCP services)
   • Runs in < 1 second

❌ What it DOES NOT do:
   • Does NOT call actual loa_common/validation.py functions
   • Does NOT connect to BigQuery
   • Does NOT read real CSV files
   • Does NOT use Apache Beam/Dataflow
   • Does NOT trigger Airflow DAGs
   • Does NOT cost any money

🎯 PURPOSE:
   Help you understand the VALIDATION PATTERN before deploying to GCP.
   This is a "conceptual demo" - the real implementation would use:
   
   Real Flow (Section 3 - Detailed Sequence Diagram):
   GCS → Composer → Dataflow → Validation → BigQuery
   
   This Test Flow:
   Python script → Mock data → Mock validation → Console output

📚 CORRESPONDING SECTIONS IN THIS DOCUMENT:
   ├─→ Section 4: DATA VALIDATION FLOW (main concept)
   ├─→ Section 3: DETAILED SEQUENCE DIAGRAM (steps 5-7b)
   ├─→ Section 6: ERROR HANDLING & RECOVERY (error isolation)
   ├─→ Section 7: MONITORING & OBSERVABILITY (metrics)
   └─→ Section 10: LOA SPECIFIC ARCHITECTURE (Processing Layer)

💡 WHAT YOU LEARNED:
   1. ✅ How validation splits records (valid vs error)
   2. ✅ What fields are validated (SSN, amount, type, date, branch)
   3. ✅ What error messages look like
   4. ✅ How metadata is added (run_id, timestamp, source)
   5. ✅ The dual-table pattern (raw + errors)

🚀 NEXT STEP: 
   To see this running FOR REAL with GCP services:
   → Follow HANDS_ON_IMPLEMENTATION_GUIDE.md
   → Deploy to Cloud Run or Dataflow
   → Use actual loa_common/validation.py module
```

---

## 0A. SIDE-BY-SIDE: Test vs Production Flow

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    LOCAL TEST                vs              PRODUCTION         │
│              (test_loa_local.py)                        (Real GCP Deployment)   │
└────────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════╦═════════════════════════════════════════════╗
║  LOCAL TEST (What you ran)    ║  PRODUCTION (What it will become)           ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  📄 Data Source               ║  📄 Data Source                             ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Hardcoded Python list:       ║  Cloud Storage (GCS):                       ║
║  test_data = [                ║  gs://loa-input/                            ║
║    ("APP001", "123-45-6789",  ║    applications_20250115_1.csv              ║
║     "John Doe", ...)          ║    applications_20250115_2.csv              ║
║  ]                            ║    applications_20250115_3.csv              ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: $0.02/GB storage                  ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  🔄 Orchestration             ║  🔄 Orchestration                           ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  None (manual run):           ║  Cloud Composer (Airflow):                  ║
║  $ python3 test_loa_local.py  ║  • GCS sensor waits for files               ║
║                               ║  • Detects split files                      ║
║                               ║  • Triggers Dataflow job                    ║
║                               ║  • Monitors completion                      ║
║                               ║  • Archives processed files                 ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: ~$100-300/month                   ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  ⚙️ Processing Engine          ║  ⚙️ Processing Engine                       ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Python script:               ║  Dataflow (Apache Beam):                    ║
║  • Loops through test data    ║  • Reads from GCS (wildcard pattern)        ║
║  • Prints validation rules    ║  • Parses CSV to dict records               ║
║  • Shows mock results         ║  • Calls loa_common/validation.py           ║
║  • No actual validation code  ║  • PCollections (parallel processing)       ║
║                               ║  • Auto-scales workers (1-100+)             ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: ~$0.10-2/hour (auto-scales)       ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  ✅ Validation Logic           ║  ✅ Validation Logic                        ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Simulated/Mock:              ║  Real implementation:                       ║
║  results = [                  ║  from loa_common import validation          ║
║    {"id": "APP001",           ║                                             ║
║     "status": "✅ VALID"}     ║  valid, errors = validation.                ║
║  ]                            ║    validate_application_record(record)      ║
║                               ║                                             ║
║  NOT ACTUALLY VALIDATING!     ║  • validate_ssn(ssn)                        ║
║  Just showing what it         ║  • validate_loan_amount(amount)             ║
║  would look like              ║  • validate_loan_type(type)                 ║
║                               ║  • validate_application_date(date)          ║
║                               ║  • validate_branch_code(branch)             ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: Included in Dataflow worker cost  ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  💾 Data Storage               ║  💾 Data Storage                            ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Console output only:         ║  BigQuery:                                  ║
║  ✅ VALID APP001              ║  • loa.applications_raw (valid records)     ║
║    → Ready for BigQuery       ║  • loa.applications_errors (errors)         ║
║  ❌ FAILED APP003             ║                                             ║
║    ❌ SSN error               ║  Each table has:                            ║
║                               ║  • Full record data                         ║
║  No actual database!          ║  • Metadata (run_id, timestamp, source)     ║
║  Just printed to screen       ║  • Partitioned by date                      ║
║                               ║  • Clustered for fast queries               ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: $20/TB storage + $5/TB queries    ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  📊 Monitoring                 ║  📊 Monitoring                              ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Summary at end:              ║  Cloud Monitoring + Logging:                ║
║  Total: 5 records             ║  • Real-time metrics (Stackdriver)          ║
║  Valid: 2 (40%)               ║  • Worker logs (per-record tracing)         ║
║  Errors: 3 (60%)              ║  • Dataflow UI (visual pipeline)            ║
║                               ║  • Custom dashboards (Looker)               ║
║  No historical tracking       ║  • Alerts (Pub/Sub notifications)           ║
║  No logs saved                ║  • SLA monitoring                           ║
║                               ║  • Cost tracking                            ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: Free tier (up to 50GB logs)       ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  🚀 Scalability                ║  🚀 Scalability                             ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  Handles: 5 records           ║  Handles: Millions of records               ║
║  Runtime: < 1 second          ║  Runtime: Auto-scales                       ║
║  Cannot handle split files    ║  • 100 records → 1 worker                   ║
║  Cannot handle large data     ║  • 1M records → 50 workers (auto)           ║
║  Single-threaded              ║  • 10M records → 500 workers (auto)         ║
║                               ║  Parallel processing across workers         ║
║                               ║                                             ║
║  💰 Cost: $0                  ║  💰 Cost: Scales with data volume           ║
║                               ║                                             ║
╠═══════════════════════════════╬═════════════════════════════════════════════╣
║                               ║                                             ║
║  🎯 Purpose                    ║  🎯 Purpose                                 ║
║  ─────────────────────────    ║  ─────────────────────────                  ║
║  LEARNING & UNDERSTANDING:    ║  PRODUCTION WORKLOAD:                       ║
║  • Show validation concept    ║  • Process real mainframe data              ║
║  • Demonstrate error handling ║  • Replace JCL/COBOL jobs                   ║
║  • Visualize data flow        ║  • Feed downstream systems                  ║
║  • Zero risk                  ║  • Meet SLAs (< 2 hours)                    ║
║  • Zero cost                  ║  • Handle split files                       ║
║  • Quick to run               ║  • 99.9% reliability                        ║
║                               ║                                             ║
╚═══════════════════════════════╩═════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────────────────┐
│                           MIGRATION PATH                                       │
└────────────────────────────────────────────────────────────────────────────────┘

   CURRENT STATE          NEXT STEP               FINAL STATE
   (You are here)         (Deploy to GCP)         (Production)
   
   ┌──────────┐           ┌──────────┐            ┌──────────┐
   │  Local   │           │   GCP    │            │   Full   │
   │   Test   │    →      │  Pilot   │     →      │  Scale   │
   │  (Demo)  │           │ (1 job)  │            │ (4 jobs) │
   └──────────┘           └──────────┘            └──────────┘
   
   • Manual run          • Cloud Storage         • All 4 JCL jobs
   • 5 records          • BigQuery (real)       • Production data
   • Mock validation    • Dataflow              • APIs exposed
   • Console output     • 1 DAG (applications)  • Mainframe retired
   • $0 cost            • Free tier             • Full monitoring
   • 0 risk             • Low risk              • Business critical
   
   Duration: 1 sec       Duration: 2-3 weeks     Duration: 2-3 months
   Cost: $0              Cost: $0-50 (free tier) Cost: $500-1000/mo
   
┌────────────────────────────────────────────────────────────────────────────────┐
│                           KEY INSIGHTS                                         │
└────────────────────────────────────────────────────────────────────────────────┘

1. test_loa_local.py is a CONCEPTUAL DEMO
   → Shows WHAT the validation does, not HOW it does it
   → Like a blueprint or wireframe

2. It demonstrates Section 4 (DATA VALIDATION FLOW) locally
   → Without requiring GCP account
   → Without any infrastructure
   → Without any cost

3. The REAL implementation uses actual modules:
   → loa_common/validation.py (you can read this file!)
   → loa_common/schema.py
   → loa_pipelines/loa_jcl_template.py

4. To go from TEST → PRODUCTION:
   → Set up GCP project
   → Deploy Dataflow pipeline
   → Create BigQuery tables
   → Set up Composer DAG
   → Run with real data

5. The validation PATTERN is the same:
   ✓ Parse CSV → Validate fields → Split valid/error → Write to tables
   (Local test shows the pattern, production implements it at scale)
```

---

## 1. LEGACY MAINFRAME FLOW (Current State)

```
┌─────────────────────────────────────────────────────────────────┐
│                     MAINFRAME ENVIRONMENT                        │
└─────────────────────────────────────────────────────────────────┘

Step 1: Job Scheduling
┌──────────────┐
│   Scheduler  │  ← JCL scheduled daily/weekly
│   (CRON/TWS) │
└──────┬───────┘
       │
       ↓
Step 2: Data Extraction
┌──────────────┐
│  JCL Job     │  ← Reads from Teradata GDW
│  COBOL       │  ← Complex business logic
│  Programs    │  ← Transforms data
└──────┬───────┘
       │
       ↓
Step 3: Output Generation
┌──────────────────┐
│  Flat Files      │  ← applications_20250115_1.txt
│  (Split Files)   │  ← applications_20250115_2.txt
│                  │  ← Large files split into chunks
└──────┬───────────┘
       │
       ↓
Step 4: File Distribution
┌──────────────────┐
│  FTP/MFT         │  ← Transfer to downstream systems
│  File Transfer   │
└──────┬───────────┘
       │
       ├─────────────→ CERDOS (Credit Risk)
       │
       ├─────────────→ FYCO (Decision Engine)
       │
       └─────────────→ GDW (Data Warehouse)

⚠️ PAIN POINTS:
   • JCL/COBOL difficult to maintain
   • Split file management complex
   • Limited monitoring/logging
   • Hard to scale
   • Long processing times
   • Brittle error handling
```

---

## 2. TARGET GCP FLOW (Future State)

```
┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD PLATFORM                         │
└─────────────────────────────────────────────────────────────────┘

Step 1: Data Ingestion
┌──────────────────┐
│  Cloud Storage   │  ← Landing zone for files
│  (GCS Buckets)   │  ← applications_20250115_*.csv
│                  │  ← gs://loa-input/
└──────┬───────────┘
       │ File arrival triggers...
       ↓
Step 2: Orchestration
┌──────────────────┐
│  Cloud Composer  │  ← Airflow DAGs
│  (Apache Airflow)│  ← Job scheduling
│                  │  ← Workflow management
└──────┬───────────┘
       │ Triggers...
       ↓
Step 3: Processing
┌──────────────────┐
│  Dataflow        │  ← Apache Beam pipelines
│  (Apache Beam)   │  ← Python-based validation
│                  │  ← Auto-scaling workers
│                  │  ← Handles split files
└──────┬───────────┘
       │
       ├─── Valid Records ────→ ┌──────────────┐
       │                        │  BigQuery    │
       │                        │  Raw Table   │
       │                        └──────────────┘
       │
       └─── Invalid Records ──→ ┌──────────────┐
                                 │  BigQuery    │
                                 │  Error Table │
                                 └──────────────┘
       ↓
Step 4: Data Quality & Transformation
┌──────────────────┐
│  dbt             │  ← SQL transformations
│  (Data Build Tool)│ ← Data quality tests
│                  │  ← Business logic
└──────┬───────────┘
       │
       ↓
Step 5: Analytics & APIs
┌──────────────────┐
│  BigQuery        │  ← Analytical queries
│  Analytics       │  ← Data warehouse
└──────┬───────────┘
       │
       ├─────────────→ Cloud Run (APIs)
       │               ↓
       │               Microservices expose data
       │
       ├─────────────→ Looker/Data Studio (Dashboards)
       │
       └─────────────→ Downstream Systems (via APIs)

✅ BENEFITS:
   • Python-based (easy to maintain)
   • Auto-scaling (handles any volume)
   • Built-in monitoring (Cloud Logging/Monitoring)
   • Serverless (no infrastructure management)
   • Fast processing (parallel workers)
   • Robust error handling (separate error table)
```

---

## 3. DETAILED SEQUENCE DIAGRAM: End-to-End Flow

```
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│   Cloud    │  │   Cloud    │  │  Dataflow  │  │  BigQuery  │  │  Cloud Run │
│  Storage   │  │  Composer  │  │            │  │            │  │   (APIs)   │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │               │               │
      │ 1. File       │               │               │               │
      │    arrives    │               │               │               │
      ├──────────────>│               │               │               │
      │               │               │               │               │
      │               │ 2. Detect     │               │               │
      │               │    file(s)    │               │               │
      │               │    (handles   │               │               │
      │               │    splits)    │               │               │
      │               │               │               │               │
      │               │ 3. Trigger    │               │               │
      │               │    Dataflow   │               │               │
      │               ├──────────────>│               │               │
      │               │               │               │               │
      │               │               │ 4. Read files │               │
      │<──────────────┼───────────────┤    from GCS   │               │
      │               │               │               │               │
      │               │               │ 5. Parse CSV  │               │
      │               │               │    records    │               │
      │               │               │               │               │
      │               │               │ 6. Validate   │               │
      │               │               │    each record│               │
      │               │               │    (SSN, loan,│               │
      │               │               │    dates, etc)│               │
      │               │               │               │               │
      │               │               │ 7a. Write     │               │
      │               │               │     valid     │               │
      │               │               ├──────────────>│               │
      │               │               │  (raw table)  │               │
      │               │               │               │               │
      │               │               │ 7b. Write     │               │
      │               │               │     errors    │               │
      │               │               ├──────────────>│               │
      │               │               │  (error table)│               │
      │               │               │               │               │
      │               │ 8. Job        │               │               │
      │               │    complete   │               │               │
      │               │<──────────────┤               │               │
      │               │               │               │               │
      │               │ 9. Archive    │               │               │
      │               │    processed  │               │               │
      │               │    files      │               │               │
      │<──────────────┤               │               │               │
      │  (moved to    │               │               │               │
      │   archive/)   │               │               │               │
      │               │               │               │               │
      │               │ 10. Data      │               │               │
      │               │     quality   │               │               │
      │               │     checks    │               │               │
      │               ├───────────────┼──────────────>│               │
      │               │               │  (count rows) │               │
      │               │               │               │               │
      │               │               │               │ 11. API       │
      │               │               │               │     requests  │
      │               │               │               │<──────────────┤
      │               │               │               │               │
      │               │               │               │ 12. Query data│
      │               │               │               ├──────────────>│
      │               │               │               │               │
      │               │ 13. Send      │               │               │
      │               │     notification│             │               │
      │               │     (Pub/Sub) │               │               │
      │               │               │               │               │
      ↓               ↓               ↓               ↓               ↓
```

---

## 4. DATA VALIDATION FLOW

```
┌───────────────────────────────────────────────────────────────────┐
│                    VALIDATION PIPELINE                            │
└───────────────────────────────────────────────────────────────────┘

Input: Raw CSV Record
┌─────────────────────────────────────────────┐
│ APP001,123-45-6789,John Doe,50000,          │
│ MORTGAGE,2025-01-15,NY1234                  │
└─────────────────┬───────────────────────────┘
                  │
                  ↓
Step 1: Parse to Dictionary
┌─────────────────────────────────────────────┐
│ {                                           │
│   'application_id': 'APP001',               │
│   'ssn': '123-45-6789',                     │
│   'applicant_name': 'John Doe',             │
│   'loan_amount': '50000',                   │
│   'loan_type': 'MORTGAGE',                  │
│   'application_date': '2025-01-15',         │
│   'branch_code': 'NY1234'                   │
│ }                                           │
└─────────────────┬───────────────────────────┘
                  │
                  ↓
Step 2: Validate Each Field
┌─────────────────────────────────────────────┐
│                                             │
│  ✓ SSN Validation                          │
│    • Format: XXX-XX-XXXX                   │
│    • Not all zeros                         │
│    • Valid area number                     │
│                                             │
│  ✓ Loan Amount Validation                  │
│    • Numeric                                │
│    • Range: $1 - $1,000,000                │
│                                             │
│  ✓ Loan Type Validation                    │
│    • Must be in allowed list               │
│                                             │
│  ✓ Date Validation                         │
│    • Format: YYYY-MM-DD                    │
│    • Not future                            │
│    • Not > 5 years old                     │
│                                             │
│  ✓ Branch Code Validation                  │
│    • Format: AA1234                        │
│    • Length: 6-8 chars                     │
│                                             │
└─────────────────┬───────────────────────────┘
                  │
                  ├─── All Valid? ────────────→ ✅ VALID PATH
                  │                              │
                  │                              ↓
                  │                        ┌──────────────┐
                  │                        │  Enrich with │
                  │                        │  metadata:   │
                  │                        │  • run_id    │
                  │                        │  • timestamp │
                  │                        │  • source    │
                  │                        └──────┬───────┘
                  │                               │
                  │                               ↓
                  │                        ┌──────────────┐
                  │                        │  BigQuery    │
                  │                        │  Raw Table   │
                  │                        └──────────────┘
                  │
                  └─── Any Errors? ───────────→ ❌ ERROR PATH
                                                 │
                                                 ↓
                                           ┌──────────────┐
                                           │  Capture:    │
                                           │  • Field     │
                                           │  • Value     │
                                           │  • Message   │
                                           │  • Record    │
                                           └──────┬───────┘
                                                  │
                                                  ↓
                                           ┌──────────────┐
                                           │  BigQuery    │
                                           │  Error Table │
                                           └──────────────┘
```

---

## 5. SPLIT FILE HANDLING FLOW

```
Legacy Mainframe Challenge:
┌─────────────────────────────────────────────┐
│  applications_20250115_1.txt (100K records)│
│  applications_20250115_2.txt (100K records)│
│  applications_20250115_3.txt (100K records)│
└─────────────────────────────────────────────┘
         ⚠️ How to process together?

GCP Solution:
┌─────────────────────────────────────────────┐
│  Step 1: Cloud Storage (GCS)                │
│  ─────────────────────────────────────────  │
│  gs://loa-input/applications_20250115_*.csv │
│                                             │
│  ↓                                          │
│                                             │
│  Step 2: Composer DAG Detects Split Files   │
│  ─────────────────────────────────────────  │
│  • Uses GCS sensor with prefix              │
│  • Waits for all files matching pattern     │
│  • Counts expected files                    │
│                                             │
│  ↓                                          │
│                                             │
│  Step 3: Dataflow Reads with Wildcard       │
│  ─────────────────────────────────────────  │
│  input_pattern = "gs://loa-input/           │
│                   applications_20250115_*"  │
│                                             │
│  • Beam ReadFromText handles all files      │
│  • Processes in parallel                    │
│  • Tracks source file in metadata           │
│                                             │
│  ↓                                          │
│                                             │
│  Step 4: Unified Output                     │
│  ─────────────────────────────────────────  │
│  • All records in single BigQuery table     │
│  • source_file column shows origin          │
│  • run_id ties batch together               │
│                                             │
└─────────────────────────────────────────────┘

✅ Result: Automatic handling, no manual merge!
```

---

## 6. ERROR HANDLING & RECOVERY FLOW

```
┌─────────────────────────────────────────────┐
│           ERROR SCENARIOS                   │
└─────────────────────────────────────────────┘

Scenario 1: Data Validation Error
Input: Bad SSN (000-00-0000)
   ↓
Validation catches error
   ↓
Record written to errors table
   ↓
Processing continues (doesn't stop job)
   ✅ Isolated error handling

Scenario 2: File Not Found
GCS sensor waits for file
   ↓
Timeout after configurable period
   ↓
DAG fails with clear error
   ↓
Alert sent (Pub/Sub notification)
   ⚠️ Operational visibility

Scenario 3: BigQuery Load Failure
Dataflow attempts write
   ↓
BigQuery returns error (schema mismatch)
   ↓
Dataflow retries (configurable attempts)
   ↓
If still fails: Job fails, logs detailed error
   ↓
Archive file to error/ bucket
   🔧 Recovery mechanism

Scenario 4: Partial Success
1000 records processed
   ↓
950 valid → raw table ✅
50 invalid → error table ❌
   ↓
Both writes succeed
   ↓
Data quality check: 95% success rate
   ↓
Alert if below threshold (e.g., 98%)
   📊 Quality monitoring
```

---

## 7. MONITORING & OBSERVABILITY FLOW

```
┌─────────────────────────────────────────────┐
│     MONITORING STACK                        │
└─────────────────────────────────────────────┘

Layer 1: Infrastructure
┌──────────────────┐
│ Cloud Monitoring │  ← CPU, Memory, Network
│ (Stackdriver)    │  ← Job duration
└────────┬─────────┘  ← Error rates
         │
         ↓

Layer 2: Application Logs
┌──────────────────┐
│ Cloud Logging    │  ← Dataflow worker logs
│                  │  ← Composer task logs
└────────┬─────────┘  ← Custom app logs
         │
         ↓

Layer 3: Data Quality
┌──────────────────┐
│ BigQuery Queries │  ← Row count validation
│                  │  ← Field distribution
└────────┬─────────┘  ← Business rule checks
         │
         ↓

Layer 4: Alerts
┌──────────────────┐
│ Cloud Pub/Sub    │  ← Job completion
│ Notifications    │  ← Error thresholds
└────────┬─────────┘  ← SLA breaches
         │
         ├────────→ Email
         ├────────→ Slack
         └────────→ PagerDuty

Layer 5: Dashboards
┌──────────────────┐
│ Looker/Data      │  ← Real-time metrics
│ Studio           │  ← Historical trends
└──────────────────┘  ← Custom KPIs

Key Metrics:
• Job success rate
• Processing time
• Records/second
• Error rate by type
• Cost per job
• Data freshness (SLA)
```

---

## 8. MIGRATION PHASES

```
┌─────────────────────────────────────────────────────────────┐
│                    MIGRATION JOURNEY                        │
└─────────────────────────────────────────────────────────────┘

Phase 1: DUAL RUN (Parallel Systems)
┌─────────────────┐         ┌─────────────────┐
│   Mainframe     │         │      GCP        │
│   (Primary)     │         │   (Shadow)      │
└────────┬────────┘         └────────┬────────┘
         │                           │
         ├────→ Production Data      │
         │                           │
         └────→ Copy to GCP ────────→│
                                     │
                              ┌──────▼──────┐
                              │  Comparison │
                              │  Validation │
                              └─────────────┘
                              • Row counts
                              • Aggregates
                              • Sample records
                              • Business rules

Timeline: 2-4 weeks
Goal: Validate GCP accuracy

─────────────────────────────────────────────────────────────

Phase 2: CUTOVER (Switch Primary)
┌─────────────────┐         ┌─────────────────┐
│   Mainframe     │         │      GCP        │
│   (Shadow)      │         │   (Primary)     │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │      Production Data      │
         │                           │
         └────←────────────────────  │
              (Backup only)          │
                                     │
                              ┌──────▼──────┐
                              │  Downstream │
                              │   Systems   │
                              └─────────────┘
                              • CERDOS
                              • FYCO
                              • GDW

Timeline: 1 week
Goal: GCP becomes source of truth

─────────────────────────────────────────────────────────────

Phase 3: DECOMMISSION (Retire Legacy)
                              ┌─────────────────┐
                              │      GCP        │
                              │   (Only)        │
                              └────────┬────────┘
                                       │
                                       │
                                       │
                                ┌──────▼──────┐
                                │  Downstream │
                                │   Systems   │
                                └─────────────┘

Timeline: After 1 month of stable operation
Goal: Mainframe jobs retired

✅ SUCCESS CRITERIA:
   • 99.9% job success rate
   • < 1% data discrepancy
   • < 5% cost increase
   • < 2 hour SLA met
   • Zero critical incidents
```

---

## 9. TECHNOLOGY DECISION TREE

```
┌───────────────────────────────────────────────────────────┐
│         WHEN TO USE WHICH GCP SERVICE?                    │
└───────────────────────────────────────────────────────────┘

START: What's your use case?
        │
        ├─── Batch Processing (files/datasets)
        │    │
        │    ├─── < 10 GB, simple transforms
        │    │    └──→ Use: Cloud Functions + BigQuery
        │    │         • Serverless
        │    │         • SQL-based
        │    │         • Low cost
        │    │
        │    ├─── 10 GB - 1 TB, complex logic
        │    │    └──→ Use: Dataflow (Apache Beam)  ⭐ LOA
        │    │         • Auto-scaling
        │    │         • Python/Java
        │    │         • Parallel processing
        │    │
        │    └─── > 1 TB, distributed processing
        │         └──→ Use: Dataproc (Spark)
        │              • Hadoop ecosystem
        │              • Scala/Python
        │              • Cluster-based
        │
        ├─── Streaming Data (real-time)
        │    │
        │    ├─── Simple event processing
        │    │    └──→ Use: Pub/Sub + Cloud Functions
        │    │         • Event-driven
        │    │         • Low latency
        │    │
        │    └─── Complex stream processing
        │         └──→ Use: Dataflow Streaming
        │              • Windows, triggers
        │              • Stateful processing
        │
        ├─── Data Transformation (SQL)
        │    └──→ Use: dbt (Data Build Tool)  ⭐ LOA
        │         • Version controlled SQL
        │         • Data quality tests
        │         • Documentation
        │
        ├─── Workflow Orchestration
        │    │
        │    ├─── Simple scheduling
        │    │    └──→ Use: Cloud Scheduler
        │    │         • Cron jobs
        │    │         • HTTP triggers
        │    │
        │    └─── Complex workflows
        │         └──→ Use: Cloud Composer  ⭐ LOA
        │              • Apache Airflow
        │              • DAG-based
        │              • Dependencies
        │
        ├─── APIs / Microservices
        │    │
        │    ├─── Simple HTTP endpoints
        │    │    └──→ Use: Cloud Functions
        │    │         • Pay per invocation
        │    │         • Auto-scale to zero
        │    │
        │    ├─── Containerized services
        │    │    └──→ Use: Cloud Run  ⭐ LOA
        │    │         • Any language
        │    │         • Container-based
        │    │         • Serverless
        │    │
        │    └─── Complex microservices
        │         └──→ Use: GKE (Kubernetes)
        │              • Full k8s control
        │              • Multi-container
        │              • Advanced networking
        │
        ├─── Data Storage
        │    │
        │    ├─── Files / Objects
        │    │    └──→ Use: Cloud Storage (GCS)  ⭐ LOA
        │    │         • Unstructured data
        │    │         • Cheap
        │    │
        │    ├─── Analytics / Warehouse
        │    │    └──→ Use: BigQuery  ⭐ LOA
        │    │         • SQL queries
        │    │         • Petabyte scale
        │    │         • Columnar storage
        │    │
        │    ├─── Transactional (ACID)
        │    │    └──→ Use: Cloud Spanner  ⭐ LOA
        │    │         • Global consistency
        │    │         • Horizontal scaling
        │    │         • SQL interface
        │    │
        │    └─── Key-Value / NoSQL
        │         └──→ Use: Firestore / Bigtable
        │              • Low latency
        │              • High throughput
        │
        └─── Data Migration
             │
             ├─── One-time bulk transfer
             │    └──→ Use: Storage Transfer Service
             │         • Scheduled transfers
             │         • From AWS, Azure, HTTP
             │
             ├─── Continuous replication
             │    └──→ Use: Datastream
             │         • CDC from databases
             │         • Low latency
             │
             └─── Legacy modernization
                  └──→ Use: Data Fusion  (alternative to LOA)
                       • No-code ETL
                       • Pre-built connectors
                       • Visual pipeline builder
```

---

## 10. LOA SPECIFIC ARCHITECTURE

```
┌───────────────────────────────────────────────────────────┐
│              LOA PROJECT ARCHITECTURE                     │
└───────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  INGESTION LAYER                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │   GCS        │  gs://loa-input/                     │
│  │   Buckets    │  • applications_YYYYMMDD_*.csv       │
│  │              │  • accounts_YYYYMMDD_*.csv           │
│  └──────┬───────┘  • transactions_YYYYMMDD_*.csv       │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │
          ↓
┌─────────┴───────────────────────────────────────────────┐
│  ORCHESTRATION LAYER                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │  Composer    │  Airflow DAGs:                       │
│  │  (Airflow)   │  • loa_applications_dag              │
│  │              │  • loa_accounts_dag                  │
│  └──────┬───────┘  • loa_transactions_dag              │
│         │                                               │
│         │  • File sensing                              │
│         │  • Split file detection                      │
│         │  • Dataflow job triggering                   │
│         │  • Data quality checks                       │
│         │  • File archival                             │
│         │  • Notifications                             │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │
          ↓
┌─────────┴───────────────────────────────────────────────┐
│  PROCESSING LAYER                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │  Dataflow    │  Apache Beam Pipelines:              │
│  │  (Beam)      │                                      │
│  │              │  ┌─────────────────────┐            │
│  │              │  │ loa_common/         │            │
│  │              │  │ • validation.py     │            │
│  │              │  │ • schema.py         │            │
│  │              │  │ • io_utils.py       │            │
│  │              │  └─────────────────────┘            │
│  │              │                                      │
│  │              │  ┌─────────────────────┐            │
│  │              │  │ loa_pipelines/      │            │
│  │              │  │ • loa_jcl_template  │            │
│  │              │  │ • applications_pipe │            │
│  │              │  │ • accounts_pipeline │            │
│  │              │  └─────────────────────┘            │
│  └──────┬───────┘                                      │
│         │                                               │
│         │  • Read from GCS                             │
│         │  • Parse CSV                                 │
│         │  • Validate records (SSN, amounts, dates)    │
│         │  • Split valid/invalid                       │
│         │  • Enrich metadata                           │
│         │  • Write to BigQuery                         │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │
          ↓
┌─────────┴───────────────────────────────────────────────┐
│  STORAGE LAYER                                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │  BigQuery    │  Tables:                             │
│  │              │                                      │
│  │              │  RAW ZONE:                           │
│  │              │  • applications_raw                  │
│  │              │  • applications_errors               │
│  │              │  • accounts_raw                      │
│  │              │  • accounts_errors                   │
│  │              │  • transactions_raw                  │
│  │              │  • transactions_errors               │
│  │              │                                      │
│  │              │  STAGING ZONE (dbt):                 │
│  │              │  • stg_applications                  │
│  │              │  • stg_accounts                      │
│  │              │  • stg_transactions                  │
│  │              │                                      │
│  │              │  MARTS ZONE (dbt):                   │
│  │              │  • dim_customers                     │
│  │              │  • fact_loans                        │
│  │              │  • fact_transactions                 │
│  └──────┬───────┘                                      │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │
          ↓
┌─────────┴───────────────────────────────────────────────┐
│  TRANSFORMATION LAYER                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │  dbt         │  SQL Transformations:                │
│  │              │  • Clean data                        │
│  │              │  • Apply business rules              │
│  │              │  • Join datasets                     │
│  │              │  • Aggregate metrics                 │
│  │              │  • Data quality tests                │
│  └──────┬───────┘                                      │
│         │                                               │
└─────────┼───────────────────────────────────────────────┘
          │
          ↓
┌─────────┴───────────────────────────────────────────────┐
│  API / SERVING LAYER                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐     ┌──────────────┐                │
│  │  Cloud Run   │     │   Apigee X   │                │
│  │              │────→│              │                │
│  │  Python APIs │     │  API Gateway │                │
│  │  (FastAPI)   │     │              │                │
│  └──────┬───────┘     └──────┬───────┘                │
│         │                    │                         │
│         │  Microservices:    │                         │
│         │  • loan-service    │                         │
│         │  • account-service │                         │
│         │  • customer-service│                         │
│         │                    │                         │
└─────────┼────────────────────┼─────────────────────────┘
          │                    │
          ↓                    ↓
┌─────────┴────────────────────┴─────────────────────────┐
│  DOWNSTREAM SYSTEMS                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  • CERDOS (Credit Risk)                                │
│  • FYCO (Decision Engine)                              │
│  • GDW (Group Data Warehouse)                          │
│  • Internal Dashboards (Looker)                        │
│                                                         │
└─────────────────────────────────────────────────────────┘

CROSS-CUTTING CONCERNS:
┌─────────────────────────────────────────────────────────┐
│  • Monitoring: Cloud Monitoring + Logging              │
│  • Security: IAM, KMS, VPC Service Controls            │
│  • DevOps: Harness CI/CD + GitHub                     │
│  • Cost: Budget alerts, committed use discounts        │
│  • Disaster Recovery: Multi-region, backups            │
└─────────────────────────────────────────────────────────┘
```

---

## 11. DECISION MATRIX: When to Use What

| Scenario | Technology Choice | Why? |
|----------|------------------|------|
| **Simple one-time data load** | `bq load` command | Fastest, simplest |
| **Recurring file processing** | Dataflow + Composer | Orchestrated, scalable |
| **Real-time streaming** | Pub/Sub + Dataflow Streaming | Low latency |
| **SQL transformations** | dbt | Version control, testing |
| **Complex Python logic** | Dataflow | Full flexibility |
| **No-code ETL** | Data Fusion | Visual interface |
| **Database replication** | Datastream | CDC, low latency |
| **API endpoints** | Cloud Run | Serverless, any language |
| **Kubernetes workloads** | GKE | Full control |
| **Scheduled jobs** | Cloud Scheduler + Functions | Simple, cheap |

---

## 12. COST OPTIMIZATION STRATEGIES

```
┌───────────────────────────────────────────────────────────┐
│              COST BREAKDOWN (Monthly)                     │
└───────────────────────────────────────────────────────────┘

Service              Cost Driver           Optimization
─────────────────────────────────────────────────────────────
BigQuery             • Storage: $20/TB/mo  • Partition tables
                     • Queries: $5/TB      • Cluster by date
                     • Streaming: $0.01/MB • Use batch insert
                                           • Expire old data

Dataflow             • Worker hours        • Right-size workers
                     • Persistent disk     • Use Flex templates
                     • Network egress      • Process in same region
                                           • Auto-scaling

Cloud Storage        • Storage: $0.02/GB   • Lifecycle policies
                     • Operations          • Nearline for archive
                     • Network egress      • Batch operations

Composer             • Environment size    • Small env for dev
(Airflow)            • Running time        • Stop when not used
                     • Worker nodes        • Schedule efficiently

Cloud Run            • CPU/memory/time     • Optimize container
                     • Requests            • Set concurrency
                     • Network             • Minimize cold starts

─────────────────────────────────────────────────────────────
TOTAL (LOA pilot):   ~$500-1000/month with optimization
Without optimization: ~$2000-3000/month

FREE TIER USAGE FOR LEARNING:
• BigQuery: 1 TB queries/month free
• GCS: 5 GB storage free
• Cloud Functions: 2M invocations free
• Dataflow: $300 credit (new accounts)

✅ For LOA local testing: $0 (use free tier!)
```

---

## KEY TAKEAWAYS

1. **Start Simple**: Begin with Cloud Functions + BigQuery, scale to Dataflow as needed
2. **Reuse Patterns**: LOA blueprint applies to all 4 mainframe jobs
3. **Monitor Early**: Set up logging/monitoring from day 1
4. **Cost Conscious**: Use free tier for learning, optimize production
5. **Test Locally**: Run validation locally before deploying to GCP
6. **Automate**: Use Composer for orchestration, not manual triggers
7. **Version Control**: All code in Git, all infrastructure as code (Terraform)
8. **Data Quality**: Separate error table, detailed validation
9. **PII Protection**: Mask sensitive data in logs
10. **Documentation**: Keep diagrams updated as architecture evolves

---

**Next Steps:**
1. ✅ Understand these flows
2. 📚 Read service-specific docs (see appendix)
3. 🏗️ Deploy LOA blueprint to GCP
4. 🧪 Test with sample data
5. 📊 Monitor and optimize
6. 🚀 Scale to production

---

*This document is your visual guide to the LOA migration strategy.*
*Keep it handy during architecture discussions and implementation.*

