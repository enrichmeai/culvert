{{
  config(
    materialized='view',
    tags=['staging', 'loa', 'customers']
  )
}}

/*
  Staging model for customers (CUSTNOJOB)

  Demonstrates reuse of validation patterns across multiple JCL jobs
*/

with source as (
    select * from {{ source('loa_raw', 'customers_raw') }}
    where customer_since >= date_sub(current_date(), interval {{ var('lookback_days') }} day)
),

cleaned as (
    select
        -- IDs
        customer_id,
        account_number,

        -- PII (handled consistently across all entities)
        ssn,
        customer_name,
        email,
        phone,

        -- Financial info
        credit_score,
        customer_since,
        branch_code,

        -- Metadata (standard across all pipelines)
        run_id,
        processed_timestamp,
        source_file,

        -- Calculated fields
        date_diff(current_date(), customer_since) as customer_tenure_days,

        -- Credit score category
        case
            when credit_score >= 800 then 'Excellent'
            when credit_score >= 740 then 'Very Good'
            when credit_score >= 670 then 'Good'
            when credit_score >= 580 then 'Fair'
            else 'Poor'
        end as credit_category,

        -- Data quality
        case
            when ssn is null then true
            when account_number is null then true
            when credit_score is null then true
            else false
        end as has_missing_fields,

        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

