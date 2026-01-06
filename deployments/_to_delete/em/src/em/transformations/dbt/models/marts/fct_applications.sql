{{
  config(
    materialized='table',
    partition_by={
      "field": "application_date",
      "data_type": "date"
    },
    cluster_by=['loan_type', 'branch_code'],
    tags=['marts', 'loa', 'fact']
  )
}}

/*
  Fact table for loan applications

  Purpose: Core fact table for loan application analytics
  Grain: One row per application
  Source: stg_applications
  Target: loa_marts.fct_applications

  Features:
  - Partitioned by application_date for performance
  - Clustered by loan_type and branch_code
  - Includes derived metrics
  - Ready for downstream analytics
*/

with applications as (
    select * from {{ ref('stg_applications') }}
),

enriched as (
    select
        -- Primary key
        application_id,

        -- Dimensions
        loan_type,
        branch_code,
        application_date,
        application_year,
        application_month,
        application_day_of_week,
        loan_amount_category,

        -- Measures
        loan_amount,
        processing_lag_days,

        -- Flags
        has_missing_fields,

        -- Applicant (aggregated/masked for privacy)
        case
            when ssn is not null then 'Y'
            else 'N'
        end as has_ssn,

        case
            when applicant_name is not null then 'Y'
            else 'N'
        end as has_applicant_name,

        -- Metadata
        run_id,
        processed_timestamp,
        source_file,

        -- Audit fields
        current_timestamp() as dbt_updated_at

    from applications
)

select * from enriched

