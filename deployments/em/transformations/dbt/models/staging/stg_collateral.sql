{{
  config(
    materialized='view',
    tags=['staging', 'loa', 'collateral']
  )
}}

/*
  Staging model for collateral (COLLATERAL)

  Demonstrates reuse of validation patterns across multiple JCL jobs
*/

with source as (
    select * from {{ source('loa_raw', 'collateral_raw') }}
    where appraisal_date >= date_sub(current_date(), interval {{ var('lookback_days') }} day)
),

cleaned as (
    select
        -- IDs
        collateral_id,
        application_id,
        account_number,
        branch_code,

        -- Collateral details
        collateral_type,
        collateral_value,
        appraisal_date,
        appraiser_name,

        -- Metadata (standard across all pipelines)
        run_id,
        processed_timestamp,
        source_file,

        -- Calculated fields
        extract(year from appraisal_date) as appraisal_year,
        extract(month from appraisal_date) as appraisal_month,

        -- Value category
        case
            when collateral_value < 50000 then 'Low Value'
            when collateral_value >= 50000 and collateral_value < 250000 then 'Medium Value'
            when collateral_value >= 250000 and collateral_value < 500000 then 'High Value'
            else 'Very High Value'
        end as value_category,

        -- Collateral to loan ratio (will join with applications in mart)
        collateral_value as collateral_amount,

        -- Data quality
        case
            when collateral_type is null then true
            when collateral_value is null then true
            when appraisal_date is null then true
            else false
        end as has_missing_fields,

        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

