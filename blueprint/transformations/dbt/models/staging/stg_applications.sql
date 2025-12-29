{{
  config(
    materialized='view',
    tags=['staging', 'loa', 'applications']
  )
}}

/*
  Staging model for loan applications

  Purpose: Clean and standardize raw application data
  Source: loa_migration.applications_raw (from Dataflow pipeline)
  Target: loa_staging.stg_applications

  Transformations:
  - Standardize field names
  - Add calculated fields
  - Filter out test records
  - Add data quality flags
*/

with source as (
    select *
    from {{ source('loa_raw', 'applications_raw') }}
    where application_date >= date_sub(current_date(), interval {{ var('lookback_days') }} day)
),

cleaned as (
    select
        -- IDs and metadata
        run_id,
        processed_timestamp,
        source_file,
        application_id,

        -- Applicant information (PII)
        ssn,
        applicant_name,

        -- Loan details
        loan_amount,
        loan_type,
        application_date,
        branch_code,

        -- Calculated fields
        extract(year from application_date) as application_year,
        extract(month from application_date) as application_month,
        extract(dayofweek from application_date) as application_day_of_week,

        -- Loan amount categories
        case
            when loan_amount < 10000 then 'Small'
            when loan_amount >= 10000 and loan_amount < 50000 then 'Medium'
            when loan_amount >= 50000 and loan_amount < 250000 then 'Large'
            else 'Very Large'
        end as loan_amount_category,

        -- Processing metrics
        timestamp_diff(
            processed_timestamp,
            timestamp(application_date),
            day
        ) as processing_lag_days,

        -- Data quality flags
        case
            when ssn is null then true
            when loan_amount is null then true
            when loan_type is null then true
            when application_date is null then true
            when branch_code is null then true
            else false
        end as has_missing_fields,

        -- Record timestamp
        current_timestamp() as dbt_updated_at

    from source
    -- Exclude test/invalid records
    where application_id not like 'TEST%'
      and application_id not like '%DUMMY%'
)

select * from cleaned

