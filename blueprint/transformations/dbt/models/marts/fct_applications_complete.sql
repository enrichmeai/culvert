{{
  config(
    materialized='table',
    partition_by={
      "field": "application_date",
      "data_type": "date"
    },
    cluster_by=['loan_type', 'branch_code', 'credit_category', 'region'],
    tags=['marts', 'loa', 'fact', 'all-entities']
  )
}}

/*
  Complete fact table with ALL 4 JCL jobs integrated

  Demonstrates the full power of multi-JCL migration:
  - LOAJOB → applications
  - CUSTNOJOB → customers
  - BRANCHJOB → branches
  - COLLATERAL → collateral

  Shows how reusable validation and consistent patterns enable
  seamless cross-entity analytics and complete 360° view
*/

with applications as (
    select * from {{ ref('stg_applications') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

branches as (
    select * from {{ ref('stg_branches') }}
),

collateral as (
    select * from {{ ref('stg_collateral') }}
),

-- Aggregate collateral per application
collateral_summary as (
    select
        application_id,
        count(*) as collateral_count,
        sum(collateral_value) as total_collateral_value,
        string_agg(collateral_type, ', ') as collateral_types
    from collateral
    group by application_id
),

complete_view as (
    select
        -- Application data (LOAJOB)
        a.application_id,
        a.loan_type,
        a.loan_amount,
        a.loan_amount_category,
        a.application_date,
        a.application_year,
        a.application_month,
        a.processing_lag_days,

        -- Customer data (CUSTNOJOB)
        c.customer_id,
        c.customer_name,
        c.account_number,
        c.credit_score,
        c.credit_category,
        c.customer_tenure_days,
        c.customer_since,

        -- Branch data (BRANCHJOB)
        b.branch_code,
        b.branch_name,
        b.region,
        b.state,
        b.city,
        b.branch_size,
        b.branch_age_days,
        b.employee_count,

        -- Collateral data (COLLATERAL) - aggregated
        col.collateral_count,
        col.total_collateral_value,
        col.collateral_types,

        -- Derived metrics using ALL entities
        case
            when c.credit_score >= 740
                 and a.loan_amount <= 250000
                 and col.total_collateral_value >= a.loan_amount * 1.2
            then 'Low Risk'
            when c.credit_score >= 670
                 and a.loan_amount <= 500000
                 and col.total_collateral_value >= a.loan_amount
            then 'Medium Risk'
            when col.total_collateral_value < a.loan_amount * 0.8
            then 'Very High Risk'
            else 'High Risk'
        end as risk_category,

        -- Loan to value ratio
        case
            when col.total_collateral_value > 0
            then round((a.loan_amount * 1.0 / col.total_collateral_value) * 100, 2)
            else null
        end as ltv_ratio_pct,

        -- Branch capacity indicator
        case
            when b.employee_count >= 40 then 'High Capacity'
            when b.employee_count >= 25 then 'Medium Capacity'
            else 'Low Capacity'
        end as branch_capacity,

        -- Customer loyalty indicator
        case
            when c.customer_tenure_days >= 3650 then 'Loyal (10+ years)'
            when c.customer_tenure_days >= 1825 then 'Established (5-10 years)'
            when c.customer_tenure_days >= 365 then 'Regular (1-5 years)'
            else 'New (<1 year)'
        end as customer_loyalty,

        -- Combined quality flags
        a.has_missing_fields as application_incomplete,
        c.has_missing_fields as customer_incomplete,
        b.has_missing_fields as branch_incomplete,
        case
            when a.has_missing_fields
                 or c.has_missing_fields
                 or b.has_missing_fields
            then true
            else false
        end as has_any_quality_issues,

        -- Metadata (shows all 4 pipelines contributed)
        a.run_id as application_run_id,
        c.run_id as customer_run_id,
        b.run_id as branch_run_id,
        a.processed_timestamp as application_processed_at,

        -- Audit
        current_timestamp() as dbt_updated_at

    from applications a
    left join customers c on a.ssn = c.ssn  -- Validated by loa_common
    left join branches b on a.branch_code = b.branch_code  -- Validated by loa_common
    left join collateral_summary col on a.application_id = col.application_id
)

select * from complete_view

/*
  This model demonstrates:
  ✅ All 4 JCL jobs working together seamlessly
  ✅ Shared validation framework (branch_code validated once, used 4x)
  ✅ Complex risk scoring using multiple entities
  ✅ Complete 360° customer view
  ✅ Production-ready analytics
  ✅ Reusable patterns scale to N entities
*/

