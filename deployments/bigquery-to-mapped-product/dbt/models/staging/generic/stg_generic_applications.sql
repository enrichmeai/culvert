{{
    config(
        materialized='view',
        tags=['staging', 'generic', 'applications']
    )
}}

/*
  Staging model for Generic Applications

  Source: odp_generic.applications
  Transformations:
  - Standardise status field name (status → application_status)
  - Map account type codes to descriptions
*/

with source as (
    select * from {{ source('odp_generic', 'applications') }}
    {% if is_incremental() %}
    where _processed_at > (select max(_processed_at) from {{ this }})
    {% endif %}
),

cleaned as (
    select
        application_id,
        customer_id,
        loan_amount,
        interest_rate,
        term_months,
        application_date,
        status                  as application_status,
        event_type,
        account_type,

        -- Audit columns
        _run_id,
        _source_file,
        _processed_at,
        _extract_date,

        current_timestamp()     as dbt_updated_at

    from source
)

select * from cleaned
