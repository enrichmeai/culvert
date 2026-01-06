{{
  config(
    materialized='table',
    partition_by={
      "field": "application_date",
      "data_type": "date"
    },
    cluster_by=['loan_type', 'branch_code', 'credit_category'],
    tags=['marts', 'loa', 'fact', 'cross-entity']
  )
}}

/*
  Enhanced fact table with cross-table joins

  Demonstrates how multiple migrated JCL jobs come together:
  - LOAJOB → applications
  - CUSTNOJOB → customers
  - BRANCHJOB → branches (when added)
  - COLLATERAL → collateral (when added)

  Shows the power of reusable validation and consistent data structures
*/

with applications as (
    select * from {{ ref('stg_applications') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

enriched as (
    select
        -- Application data
        a.application_id,
        a.loan_type,
        a.loan_amount,
        a.loan_amount_category,
        a.application_date,
        a.application_year,
        a.application_month,
        a.branch_code,

        -- Customer enrichment (from CUSTNOJOB pipeline)
        c.customer_id,
        c.customer_name,
        c.account_number,
        c.credit_score,
        c.credit_category,
        c.customer_tenure_days,
        c.customer_since,

        -- Derived metrics
        case
            when c.credit_score >= 740 and a.loan_amount <= 250000 then 'Low Risk'
            when c.credit_score >= 670 and a.loan_amount <= 500000 then 'Medium Risk'
            else 'High Risk'
        end as risk_category,

        -- Combined flags
        a.has_missing_fields as application_incomplete,
        c.has_missing_fields as customer_incomplete,

        -- Metadata (consistent across all entities)
        a.run_id as application_run_id,
        c.run_id as customer_run_id,
        a.processed_timestamp,

        -- Audit
        current_timestamp() as dbt_updated_at

    from applications a
    left join customers c on a.ssn = c.ssn  -- PII join (both validated by loa_common)
)

select * from enriched

/*
  Future enhancement (when branches and collateral pipelines are added):

  LEFT JOIN branches b ON a.branch_code = b.branch_code
  LEFT JOIN collateral col ON a.application_id = col.application_id

  This shows how the reusable framework scales to N entities!
*/

