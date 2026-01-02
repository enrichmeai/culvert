# LOA Blueprint - Complete Component Overview

## 📦 Component Architecture

The LOA (Application B Application) Blueprint is a **production-ready reference implementation** for migrating mainframe JCL jobs to Google Cloud Platform using Apache Beam/Dataflow.

---

## 🏗️ Core Components

### 1. **Pipeline Engine** (`loa_pipelines/`)

#### **loa_jcl_template.py** (553 lines)
**Purpose:** Main Apache Beam/Dataflow pipeline for processing loan applications

**Features:**
- Reads CSV files from Google Cloud Storage (handles split files)
- Parses and validates loan application records
- Enriches data with metadata (run_id, timestamp, source_file)
- Writes valid records to BigQuery `applications_raw`
- Writes errors to BigQuery `applications_errors`
- Supports DirectRunner (local, FREE) and DataflowRunner (cloud, scalable)

**Key Classes:**
- `ParseCsvLine` - CSV parsing DoFn
- `ValidateAndEnrich` - Validation and metadata enrichment DoFn
- `run_pipeline()` - Main orchestration function

**Use Cases:**
- Batch processing of mainframe flat files
- Data quality validation
- ETL pipelines with error isolation

---

#### **dag_template.py**
**Purpose:** Cloud Composer/Airflow DAG factory for orchestration

**Features:**
- Creates parameterized DAGs for multiple JCL jobs
- File detection and scheduling
- Pipeline triggering and monitoring
- Data quality checks
- File archiving after processing

**Use Cases:**
- Scheduled batch processing (daily, hourly)
- Complex workflows with dependencies
- Production orchestration

---

### 2. **Validation Framework** (`loa_domain/validation.py`)

**Purpose:** Centralized field-level and record-level validation

**Validators:**
1. **SSN Validator**
   - Format: XXX-XX-XXXX (9 digits)
   - Cannot be all zeros or same digit
   - Area number validation (no 000, 666, 900-999)

2. **Loan Amount Validator**
   - Must be numeric
   - Range: $1 to $1,000,000
   - Business rule enforcement

3. **Loan Type Validator**
   - Allowed values: MORTGAGE, PERSONAL, AUTO, HOME_EQUITY
   - Case-sensitive validation

4. **Application Date Validator**
   - Format: YYYY-MM-DD
   - Cannot be in the future
   - Cannot be more than 5 years old

5. **Branch Code Validator**
   - 6-8 alphanumeric characters
   - Format: 1-2 letters + 1-6 digits (e.g., NY1234)

**Key Functions:**
- `validate_application_record()` - Complete record validation
- `ValidationError` dataclass - Structured error reporting
- PII masking in error messages

**Reusability:**
- Easy to add new validators
- Can be imported into any pipeline
- Clear separation of business logic

---

### 3. **Schema Management** (`loa_domain/schema.py`)

**Purpose:** BigQuery schema definitions and DDL generation

**Schemas:**
1. **applications_raw** (10 fields)
   - Valid loan application records
   - Partitioned by `processed_timestamp` (daily)
   - Clustered by `application_date`, `loan_type`
   - Optimized for analytical queries

2. **applications_errors** (8 fields)
   - Validation error records
   - Partitioned by `processed_timestamp`
   - Includes error details and raw record

**Key Functions:**
- `get_applications_raw_schema()` - Returns BigQuery schema
- `get_applications_errors_schema()` - Returns error table schema
- `validation_error_to_bq_row()` - Converts errors to BigQuery rows
- `record_to_bq_compatible()` - Type conversions
- `get_applications_raw_ddl()` - Generates DDL statements

**Benefits:**
- Single source of truth for schemas
- Easy schema evolution
- Automatic DDL generation

---

### 4. **I/O Utilities** (Integrated in `gdw_data_core`)

**Purpose:** Helper functions for GCS and Pub/Sub operations provided by the core library.

**Features:**
- GCS file listing and wildcard matching
- File archiving after processing
- Pub/Sub message publishing for notifications
- Run ID generation (unique identifiers)
- Metadata helpers

**Key Classes/Functions:**
- `generate_run_id()` - Creates unique run identifiers
- `PubSubClient` - Pub/Sub notification client
- GCS helper functions

---

### 5. **Cloud Functions** (`cloud-functions/`)

#### **loa-auto-trigger/**
**Purpose:** Automatically trigger pipeline when files are uploaded

**Features:**
- Listens for CSV uploads to GCS bucket
- Event-driven pipeline triggering
- Logs all trigger events
- Configurable via environment variables

**Components:**
- `main.py` - Cloud Function entry point
- `requirements.txt` - Python dependencies
- `README.md` - Deployment guide

**Use Cases:**
- Real-time file processing
- Event-driven architecture
- Automatic pipeline orchestration

**Cost:** ~$0.10-1/month

---

### 6. **Deployment Scripts** (`scripts/`)

#### **gcp-deploy.sh**
**Purpose:** Main deployment script with Cloud Function integration

**Features:**
- Enables required GCP APIs
- Creates Cloud Storage buckets (data, archive, temp)
- Creates BigQuery dataset and tables
- Creates Pub/Sub topics
- Uploads sample data
- **Optional Step 7:** Deploy Cloud Function (prompts user)
- Idempotent (safe to re-run)

---

#### **deploy-cloud-function.sh**
**Purpose:** Standalone Cloud Function deployment

**Features:**
- Checks and enables Cloud Functions API
- Grants Eventarc permissions
- Deploys with proper environment variables
- Configures bucket triggers

---

#### **deploy-dataflow.sh**
**Purpose:** Deploy Apache Beam pipeline to Dataflow

**Features:**
- Installs dependencies
- Configures DataflowRunner
- Sets project and region
- Handles temporary storage

---

#### **setup-auto-trigger.sh**
**Purpose:** Interactive Cloud Function setup wizard

**Features:**
- User-friendly prompts
- Cost information
- Calls deploy-cloud-function.sh
- Can be run anytime after initial deployment

---

### 7. **Testing Components**

#### **test_loa_local.py**
**Purpose:** Local validation testing (no GCP required)

**Features:**
- Tests validation logic with sample data
- Shows expected vs. actual results
- Displays validation rules
- Shows BigQuery schema
- Demonstrates data flow

**Output:** Visual report with pass/fail results

---

#### **trigger-pipeline-now.sh**
**Purpose:** Manual pipeline trigger script

**Features:**
- Checks for input files in GCS
- Verifies dependencies
- Runs DirectRunner pipeline (FREE)
- Shows results summary
- Queries BigQuery for verification

**Use Cases:**
- Testing and development
- On-demand processing
- Learning and demos

---

#### **setup-dependencies.sh**
**Purpose:** Install Python dependencies

**Features:**
- Installs Apache Beam 2.49.0
- Installs Google Cloud clients
- Installs LOA validation modules
- Verifies installation

**Time:** 2-3 minutes (one-time)

---

### 8. **Sample Data** (`data/input/`)

#### **applications_20250119_1.csv**
**Purpose:** Sample loan application data (5 records)

**Records:**
- 5 loan applications (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)
- Mix of valid and invalid data for testing
- Realistic field values
- Demonstrates validation rules

**Use Cases:**
- Testing pipeline locally
- Demonstrating validation
- Training new team members

---

## 🎯 Supporting Components

### 9. **Documentation** (15+ guides)

#### **Getting Started**
- `GETTING_STARTED.md` - Complete walkthrough
- `README_START_HERE.md` - Quick start guide
- `QUICK_REFERENCE_CARD.txt` - Command reference (print-ready)
- `INDEX.md` - Master documentation index

#### **Deployment**
- `DEPLOYMENT_WORKFLOW.md` - Complete workflow with diagrams
- `DEPLOYMENT_COMPLETE_SUMMARY.md` - Deployment status
- `GCP_DEPLOYMENT_QUICKSTART.md` - Quick deployment guide
- `DEPLOYMENT_FIX.md` - Troubleshooting guide

#### **Pipeline Operation**
- `HOW_TO_TRIGGER_PIPELINE.md` - All trigger methods
- `TRIGGER_QUICK_START.md` - Quick trigger reference
- `FILE_UPLOAD_AND_TRIGGERING.md` - Upload and trigger guide
- `PIPELINE_SUMMARY.md` - Complete pipeline details

#### **Architecture**
- `LOA_VISUAL_ARCHITECTURE.md` - Architecture diagrams
- `HOW_LOA_WORKS_AND_REUSE.md` - How to reuse patterns
- `MIGRATION_PATTERN.md` - Migration patterns

#### **Cloud Function**
- `CLOUD_FUNCTION_COMMIT_GUIDE.md` - Commit guide
- `CLOUD_FUNCTION_PERMISSION_FIX.md` - Permission fixes
- `WORKFLOW_INTEGRATION_SUMMARY.md` - Integration details

#### **Project Management**
- `PROJECT_DELETED.md` - Deletion status
- `GCP_RESOURCES_CREATED.md` - Resource inventory

---

### 10. **Configuration Files**

#### **requirements.txt**
**Purpose:** Python dependencies for production

**Key Dependencies:**
- `apache-beam[gcp]==2.49.0` - Pipeline framework
- `google-cloud-bigquery` - BigQuery client
- `google-cloud-storage` - GCS client
- `google-cloud-pubsub` - Pub/Sub client
- And more...

---

#### **requirements-ci.txt**
**Purpose:** Dependencies for CI/CD pipeline

---

#### **.gitignore**
**Purpose:** Git ignore rules for Python projects

**Excludes:**
- Python cache files
- Virtual environments
- IDE configs
- Credentials
- Large data files

---

## 🔄 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT                                                           │
│  Mainframe JCL → Flat Files → GCS Bucket                       │
│  gs://loa-migration-dev-loa-data/input/applications_*.csv      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGER (3 Options)                                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Manual:           ./trigger-pipeline-now.sh                 │
│  2. Cloud Function:   Auto-trigger on file upload               │
│  3. Cloud Composer:   Scheduled via Airflow DAG                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  APACHE BEAM PIPELINE                                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐                                               │
│  │ Read Files   │ → ReadFromTextWithFilename                    │
│  └──────────────┘                                               │
│         ↓                                                        │
│  ┌──────────────┐                                               │
│  │ Parse CSV    │ → ParseCsvLine DoFn                           │
│  └──────────────┘                                               │
│         ↓                                                        │
│  ┌──────────────┐                                               │
│  │ Validate     │ → ValidateAndEnrich DoFn                      │
│  │              │   • loa_common.validation                     │
│  │              │   • 5 field validators                        │
│  └──────────────┘                                               │
│         ↓                                                        │
│  ┌──────────────┐                                               │
│  │ Enrich       │ → Add metadata (run_id, timestamp, source)    │
│  └──────────────┘                                               │
│         ↓                                                        │
│  ┌──────────────┐                                               │
│  │ Route        │ → Side outputs (valid vs. errors)             │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
                    ↓                    ↓
          ┌─────────────────┐  ┌─────────────────┐
          │ Valid Records   │  │ Error Records   │
          └─────────────────┘  └─────────────────┘
                    ↓                    ↓
┌─────────────────────────────────────────────────────────────────┐
│  BIGQUERY TABLES                                                 │
├─────────────────────────────────────────────────────────────────┤
│  applications_raw            applications_errors                 │
│  • 10 fields                 • 8 fields                          │
│  • Partitioned by timestamp  • Partitioned by timestamp          │
│  • Clustered by date & type  • Error details + raw record       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  NOTIFICATION                                                    │
│  Pub/Sub: loa-processing-notifications                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Component Dependencies

```
loa_pipelines/loa_jcl_template.py
    ├── loa_common/validation.py (field validators)
    ├── loa_common/schema.py (BigQuery schemas)
    ├── loa_common/io_utils.py (GCS, Pub/Sub helpers)
    └── apache_beam (pipeline framework)

cloud-functions/loa-auto-trigger/
    └── GCS event trigger → Dataflow API

scripts/gcp-deploy.sh
    ├── scripts/deploy-cloud-function.sh (optional)
    └── GCP APIs (BigQuery, Storage, Dataflow, Pub/Sub)

trigger-pipeline-now.sh
    ├── loa_common/* (validation, schemas)
    ├── apache_beam (DirectRunner)
    └── Google Cloud credentials (ADC)
```

---

## 🎯 Component Reusability

### **Can Be Reused As-Is:**
✅ Validation framework (add new validators easily)  
✅ Schema management (adapt to new tables)  
✅ Pipeline template (change field mappings)  
✅ Deployment scripts (change project ID)  
✅ Cloud Function (change bucket/trigger)  
✅ Documentation structure  

### **Needs Customization:**
⚙️ Field names and mappings  
⚙️ Validation rules (business-specific)  
⚙️ BigQuery schemas (add/remove fields)  
⚙️ Sample data (your test cases)  

### **Template for Other Migrations:**
- Other mainframe JCL jobs
- Teradata → BigQuery migrations
- Other flat file processing
- Any CSV-based ETL pipeline

---

## 💰 Cost Breakdown by Component

| Component | Cost | Notes |
|-----------|------|-------|
| **loa_pipelines/** | $0 with DirectRunner | ~$0.50-5/hr with DataflowRunner |
| **loa_common/** | $0 | Pure Python library |
| **cloud-functions/** | ~$0.10-1/month | Optional component |
| **BigQuery Storage** | $0 | First 10 GB free |
| **BigQuery Queries** | $0 | First 1 TB/month free |
| **Cloud Storage** | $0 | First 5 GB free |
| **Pub/Sub** | $0 | First 10 GB messages free |
| **Total (Testing)** | **$0** | Using free tiers |
| **Total (Production)** | **~$10-50/month** | Depends on scale |

---

## 🔧 Technology Stack

### **Core Technologies**
- **Pipeline:** Apache Beam 2.49.0 (Python SDK)
- **Data Warehouse:** Google BigQuery
- **Storage:** Google Cloud Storage
- **Messaging:** Google Pub/Sub
- **Orchestration:** Cloud Composer (Airflow) / Cloud Functions
- **Language:** Python 3.9+

### **Supporting Tools**
- **Deployment:** Bash scripts, gcloud CLI
- **Testing:** pytest, DirectRunner
- **Version Control:** Git
- **CI/CD:** GitHub Actions (optional)
- **Monitoring:** Cloud Logging, Cloud Monitoring

---

## 📈 Scalability Profile

### **Current Configuration (Development)**
- DirectRunner (local execution)
- Small datasets (< 1000 records)
- Free Tier usage
- **Cost:** $0/month

### **Production Configuration**
- DataflowRunner (distributed execution)
- Large datasets (millions of records)
- Auto-scaling workers
- **Cost:** ~$10-50/month (depends on volume)

### **Scale Limits**
- **BigQuery:** Petabyte-scale analytics
- **Dataflow:** Auto-scales to 100s of workers
- **Cloud Storage:** Unlimited capacity
- **Pub/Sub:** Millions of messages/second

---

## ✅ Component Maturity

| Component | Status | Production Ready |
|-----------|--------|------------------|
| **loa_pipelines/** | ✅ Complete | Yes (553 lines) |
| **loa_common/** | ✅ Complete | Yes (all validators) |
| **cloud-functions/** | ✅ Complete | Yes (with permissions) |
| **scripts/** | ✅ Complete | Yes (idempotent) |
| **Documentation** | ✅ Complete | Yes (15+ guides) |
| **Tests** | ✅ Available | Yes (local + integration) |
| **Sample Data** | ✅ Available | Yes (5 records) |

---

## 🎓 Learning Resources

### **Quick Start**
1. `README_START_HERE.md` - 5-minute overview
2. `GETTING_STARTED.md` - Complete walkthrough
3. `test_loa_local.py` - Run local test (no GCP)

### **Deep Dive**
1. `PIPELINE_SUMMARY.md` - Pipeline architecture
2. `LOA_VISUAL_ARCHITECTURE.md` - Visual diagrams
3. `DEPLOYMENT_WORKFLOW.md` - Complete workflow

### **Reference**
1. `QUICK_REFERENCE_CARD.txt` - Command cheat sheet
2. `HOW_TO_TRIGGER_PIPELINE.md` - All trigger methods
3. `GCP_RESOURCES_CREATED.md` - Resource inventory

---

## 🚀 Summary

The **LOA Blueprint** is a complete, production-ready reference implementation with:

### **Core Components:**
1. ✅ Apache Beam Pipeline (553 lines)
2. ✅ Validation Framework (5 validators)
3. ✅ Schema Management (BigQuery DDL)
4. ✅ I/O Utilities (GCS, Pub/Sub)
5. ✅ Cloud Functions (auto-trigger)
6. ✅ Deployment Scripts (fully automated)
7. ✅ Testing Tools (local + GCP)
8. ✅ Sample Data (realistic examples)
9. ✅ Documentation (15+ comprehensive guides)
10. ✅ Configuration (requirements, .gitignore)

### **Key Features:**
- **Modular:** Components can be used independently
- **Reusable:** Template for other migrations
- **Scalable:** Handles small to large datasets
- **Cost-Optimized:** $0 for testing, scales efficiently
- **Well-Documented:** 15+ guides covering everything
- **Production-Ready:** All code tested and committed

### **Use Cases:**
- Mainframe JCL → GCP migration
- Teradata → BigQuery migration
- Flat file processing pipelines
- Data validation and quality checks
- ETL batch processing
- Reference architecture for your team

---

**The LOA Blueprint provides everything needed for a complete mainframe-to-cloud migration!** 🎉

---

*Last Updated: December 20, 2025*  
*All components tested, documented, and committed to git*

