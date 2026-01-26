#!/bin/bash
# =============================================================================
# Verify ODP Load and Create FDP Tables
# =============================================================================
# This script:
# 1. Loads test data into ODP tables (skipping HDR/TRL records)
# 2. Verifies ODP row counts
# 3. Creates FDP tables using simple SQL (simulating dbt)
# 4. Verifies FDP row counts
# =============================================================================

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
echo "=============================================="
echo "ODP/FDP Verification - Project: $PROJECT_ID"
echo "=============================================="

# -----------------------------------------------------------------------------
# Step 1: Load ODP Data
# -----------------------------------------------------------------------------
echo ""
echo ">>> Step 1: Load ODP Data from GCS"

# Load EM Customers
echo "Loading EM Customers..."
bq load --source_format=CSV --skip_leading_rows=1 --max_bad_records=10 --replace \
  ${PROJECT_ID}:odp_em.customers \
  gs://${PROJECT_ID}-em-landing/em/customers/em_customers.csv \
  customer_id:STRING,first_name:STRING,last_name:STRING,ssn:STRING,status:STRING,created_date:STRING

# Load EM Accounts
echo "Loading EM Accounts..."
bq load --source_format=CSV --skip_leading_rows=1 --max_bad_records=10 --replace \
  ${PROJECT_ID}:odp_em.accounts \
  gs://${PROJECT_ID}-em-landing/em/accounts/em_accounts.csv \
  account_id:STRING,customer_id:STRING,account_type:STRING,balance:FLOAT64,open_date:STRING

# Load EM Decision
echo "Loading EM Decision..."
bq load --source_format=CSV --skip_leading_rows=1 --max_bad_records=10 --replace \
  ${PROJECT_ID}:odp_em.decision \
  gs://${PROJECT_ID}-em-landing/em/decision/em_decision.csv \
  decision_id:STRING,customer_id:STRING,outcome:STRING,decision_date:STRING,score:INT64

# Load LOA Applications
echo "Loading LOA Applications..."
bq load --source_format=CSV --skip_leading_rows=1 --max_bad_records=10 --replace \
  ${PROJECT_ID}:odp_loa.applications \
  gs://${PROJECT_ID}-loa-landing/loa/applications/loa_applications.csv \
  application_id:STRING,customer_id:STRING,ssn:STRING,loan_amount:FLOAT64,interest_rate:FLOAT64,term_months:INT64,application_date:STRING,status:STRING,event_type:STRING,account_type:STRING

echo "  ✅ ODP data loaded"

# -----------------------------------------------------------------------------
# Step 2: Verify ODP Row Counts
# -----------------------------------------------------------------------------
echo ""
echo ">>> Step 2: Verify ODP Row Counts"

echo "EM ODP Tables:"
bq query --use_legacy_sql=false --format=prettyjson \
  "SELECT 'customers' as table_name, COUNT(*) as row_count FROM \`${PROJECT_ID}.odp_em.customers\`
   UNION ALL
   SELECT 'accounts', COUNT(*) FROM \`${PROJECT_ID}.odp_em.accounts\`
   UNION ALL
   SELECT 'decision', COUNT(*) FROM \`${PROJECT_ID}.odp_em.decision\`"

echo ""
echo "LOA ODP Tables:"
bq query --use_legacy_sql=false --format=prettyjson \
  "SELECT 'applications' as table_name, COUNT(*) as row_count FROM \`${PROJECT_ID}.odp_loa.applications\`"

# -----------------------------------------------------------------------------
# Step 3: Create FDP Tables (Simulating dbt transformation)
# -----------------------------------------------------------------------------
echo ""
echo ">>> Step 3: Create FDP Tables (transformation)"

# EM FDP - Customer Account Summary (join customers + accounts + decision)
echo "Creating FDP: em_customer_account_summary..."
bq query --use_legacy_sql=false --destination_table=${PROJECT_ID}:fdp_em.customer_account_summary --replace \
"SELECT
  c.customer_id,
  c.first_name,
  c.last_name,
  '***-**-' || SUBSTR(c.ssn, -4) as ssn_masked,
  c.status as customer_status,
  COUNT(a.account_id) as account_count,
  SUM(COALESCE(a.balance, 0)) as total_balance,
  MAX(d.outcome) as latest_decision,
  MAX(d.score) as latest_score,
  CURRENT_TIMESTAMP() as _processed_at
FROM \`${PROJECT_ID}.odp_em.customers\` c
LEFT JOIN \`${PROJECT_ID}.odp_em.accounts\` a ON c.customer_id = a.customer_id
LEFT JOIN \`${PROJECT_ID}.odp_em.decision\` d ON c.customer_id = d.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.ssn, c.status"

# LOA FDP - Loan Portfolio Summary
echo "Creating FDP: loa_portfolio_summary..."
bq query --use_legacy_sql=false --destination_table=${PROJECT_ID}:fdp_loa.portfolio_summary --replace \
"SELECT
  account_type,
  status,
  COUNT(*) as application_count,
  SUM(loan_amount) as total_loan_amount,
  AVG(interest_rate) as avg_interest_rate,
  AVG(term_months) as avg_term_months,
  CURRENT_TIMESTAMP() as _processed_at
FROM \`${PROJECT_ID}.odp_loa.applications\`
GROUP BY account_type, status"

echo "  ✅ FDP tables created"

# -----------------------------------------------------------------------------
# Step 4: Verify FDP Row Counts
# -----------------------------------------------------------------------------
echo ""
echo ">>> Step 4: Verify FDP Row Counts"

echo "EM FDP Tables:"
bq query --use_legacy_sql=false \
  "SELECT 'customer_account_summary' as table_name, COUNT(*) as row_count
   FROM \`${PROJECT_ID}.fdp_em.customer_account_summary\`"

echo ""
echo "LOA FDP Tables:"
bq query --use_legacy_sql=false \
  "SELECT 'portfolio_summary' as table_name, COUNT(*) as row_count
   FROM \`${PROJECT_ID}.fdp_loa.portfolio_summary\`"

# -----------------------------------------------------------------------------
# Step 5: Show Sample Data
# -----------------------------------------------------------------------------
echo ""
echo ">>> Step 5: Sample FDP Data"

echo ""
echo "EM Customer Account Summary (FDP):"
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.fdp_em.customer_account_summary\` LIMIT 5"

echo ""
echo "LOA Portfolio Summary (FDP):"
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.fdp_loa.portfolio_summary\` LIMIT 5"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "✅ VERIFICATION COMPLETE"
echo "=============================================="
echo ""
echo "ODP (Operational Data Product) - Raw 1:1 mapping:"
echo "  - odp_em.customers, odp_em.accounts, odp_em.decision"
echo "  - odp_loa.applications"
echo ""
echo "FDP (Final Data Product) - Transformed/aggregated:"
echo "  - fdp_em.customer_account_summary"
echo "  - fdp_loa.portfolio_summary"
echo ""
echo "This demonstrates the 3-Unit Architecture:"
echo "  1. Ingestion: GCS → ODP (Dataflow)"
echo "  2. Transformation: ODP → FDP (dbt/SQL)"
echo "  3. Orchestration: Airflow coordinates the flow"
echo "=============================================="
