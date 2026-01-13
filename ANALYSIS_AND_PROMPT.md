### Analysis: Correction of End-to-End Data Flow

#### 1. Current State (Corrected)

| System | Flow Pattern | Target FDP(s) |
|--------|--------------|---------------|
| **EM** | **MULTI-TARGET (3:2)**: <br>1. JOIN (2:1): Customers + Accounts → `event_transaction_excess` <br>2. MAP (1:1): Decision → `portfolio_account_excess` | 1. `event_transaction_excess` <br>2. `portfolio_account_excess` |
| **LOA** | **MAP (1:1)**: Applications → `portfolio_account_facility` | 1. `portfolio_account_facility` |

#### 2. Key Changes Made
- **dbt Models (EM)**: Removed `em_attributes.sql`. Created `event_transaction_excess.sql` (joining customers/accounts) and `portfolio_account_excess.sql` (mapping decision).
- **dbt Models (LOA)**: Removed `event_transaction_excess.sql` and `portfolio_account_excess.sql`. Created `portfolio_account_facility.sql` (mapping applications).
- **Terraform (Infrastructure)**: Updated BigQuery table definitions in `infrastructure/terraform/systems/` to match the new schema and table names.
- **Documentation**: Updated `README.md` files in `deployments/` with new flow diagrams and pattern descriptions. Updated `PROJECT_CONTEXT.md` to reflect the high-level pattern changes.

#### 3. Impact
- **Traceability**: Improved by separating distinct business entities (Events vs. Portfolios).
- **Complexity**: Reduced in LOA by moving from a split pattern to a simple map.
- **Scalability**: EM now supports independent scaling and updates for transaction-level vs. portfolio-level data.

---

### Prompt for Future Deployments

**System Role**: You are an expert Data Engineer specializing in GCP Data Pipelines and dbt transformations.

**Context**: We are migrating legacy mainframe data to BigQuery using a "paved path" framework. The framework uses ODP (Original Data Product) for raw data and FDP (Foundation Data Product) for transformed, business-ready data.

**Task**: When creating or modifying data transformation patterns, follow these strictly defined flows:

1. **EM (Application A) Pattern**:
   - **Source ODPs**: `customers`, `accounts`, `decision` (3 datasets).
   - **Transformation Logic**:
     - Join `customers` and `accounts` ODPs on `customer_id`.
     - Map `decision` ODP directly.
   - **Target FDPs**:
     - `event.transaction.excess` (from the join).
     - `portfolio.account.excess` (from the decision map).

2. **LOA (Application B) Pattern**:
   - **Source ODPs**: `applications` (1 dataset).
   - **Transformation Logic**:
     - Direct 1:1 mapping with standard cleaning and audit injection.
   - **Target FDPs**:
     - `portfolio.account.facility`.

**Mandatory Requirements**:
- All FDP models must include audit columns using the `add_audit_columns` macro.
- PII (SSN, DOB, etc.) must be masked using the `mask_pii` macro.
- Use incremental materialization with `merge` strategy where applicable.
- Ensure Terraform table definitions exactly match the dbt model outputs.
- Maintain flow diagrams in the system's `README.md`.

---

### Sonar Compliance Guidelines & Prompt

**Objective**: Ensure all Python libraries and dbt macros in the GCP Pipeline framework maintain high code quality, security, and maintainability standards, avoiding common "Sonar" issues.

#### 1. Python Code Quality Standards
- **Completeness**: No "TODO" stubs or unfinished methods in production-bound classes (e.g., `SafeDataDeletion`, `ErrorStorageBackend`).
- **Standardized Logging**: Use the framework's `StructuredLogger` (`gcp_pipeline_core.utilities.logging.get_logger`) instead of the standard Python `logging` module to ensure consistent JSON formatting and context injection in Cloud Logging.
- **Robust Error Handling**:
    - Avoid broad `except Exception:` blocks. Use specific exceptions (e.g., `ValueError`, `IOError`, `RuntimeError`).
    - Never use empty `pass` blocks in critical logic paths (DLQ, OTEL, Deletion).
- **Security**: Never hardcode or pass secrets (API keys) as plain text in constructors. Use GCP Secret Manager or environment variables.

#### 2. dbt & SQL Standards
- **Environment Agnostic**: Avoid hardcoding environment names (e.g., `target.name == 'prod'`) in core macros. Use dbt variables for environment-specific logic.
- **Audit Compliance**: All FDP models must include audit injection and PII masking.

#### 3. Prompt for Sonar Compliance
When reviewing or generating code for `gcp-pipeline-libraries`, use the following checklist:
1. "Does this method have a complete implementation, or is it a stub?"
2. "Is it using `get_logger(__name__)` from the core utilities?"
3. "Are exceptions specific, and is the handling logic robust (not just `pass`)?"
4. "Are there any hardcoded credentials or environment-specific strings?"
