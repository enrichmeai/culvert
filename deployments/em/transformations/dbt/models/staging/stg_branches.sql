{{
  config(
    materialized='view',
    tags=['staging', 'loa', 'branches']
  )
}}

/*
  Staging model for branches (BRANCHJOB)

  Demonstrates reuse of validation patterns across multiple JCL jobs
*/

with source as (
    select * from {{ source('loa_raw', 'branches_raw') }}
),

cleaned as (
    select
        -- IDs
        branch_code,

        -- Branch details
        branch_name,
        region,
        state,
        city,
        zip_code,
        manager_name,
        opened_date,
        employee_count,

        -- Metadata (standard across all pipelines)
        run_id,
        processed_timestamp,
        source_file,

        -- Calculated fields
        date_diff(current_date(), opened_date) as branch_age_days,
        extract(year from opened_date) as opened_year,

        -- Branch size category
        case
            when employee_count >= 40 then 'Large'
            when employee_count >= 30 then 'Medium'
            when employee_count >= 20 then 'Small'
            else 'Micro'
        end as branch_size,

        -- Data quality
        case
            when branch_name is null then true
            when region is null then true
            when state is null then true
            else false
        end as has_missing_fields,

        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

