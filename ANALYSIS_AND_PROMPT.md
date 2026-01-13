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
