{{
  config(
    materialized='table',
    tags=['analytics', 'loa', 'daily']
  )
}}

/*
  Daily application metrics

  Purpose: Daily aggregated metrics for monitoring and reporting
  Grain: One row per day per loan_type per branch
  Source: fct_applications
  Target: loa_analytics.daily_application_metrics

  Use Cases:
  - Daily operational dashboards
  - Volume trend analysis
  - Branch performance monitoring
  - Loan type distribution tracking
*/

with applications as (
    select * from {{ ref('fct_applications') }}
),

daily_metrics as (
    select
        -- Dimensions
        application_date,
        loan_type,
        branch_code,

        -- Volume metrics
        count(*) as application_count,
        count(distinct application_id) as unique_applications,

        -- Amount metrics
        sum(loan_amount) as total_loan_amount,
        avg(loan_amount) as avg_loan_amount,
        min(loan_amount) as min_loan_amount,
        max(loan_amount) as max_loan_amount,
        approx_quantiles(loan_amount, 2)[offset(1)] as median_loan_amount,

        -- Loan amount distribution
        countif(loan_amount_category = 'Small') as small_loan_count,
        countif(loan_amount_category = 'Medium') as medium_loan_count,
        countif(loan_amount_category = 'Large') as large_loan_count,
        countif(loan_amount_category = 'Very Large') as very_large_loan_count,

        -- Data quality metrics
        countif(has_missing_fields) as records_with_missing_fields,
        countif(has_ssn = 'Y') as records_with_ssn,
        countif(has_applicant_name = 'Y') as records_with_name,

        -- Processing metrics
        avg(processing_lag_days) as avg_processing_lag_days,
        max(processing_lag_days) as max_processing_lag_days,

        -- Completeness score (%)
        round(
            (countif(not has_missing_fields) * 100.0) / count(*),
            2
        ) as completeness_score_pct,

        -- Audit
        current_timestamp() as dbt_updated_at

    from applications
    group by 1, 2, 3
)

select * from daily_metrics
order by application_date desc, loan_type, branch_code

