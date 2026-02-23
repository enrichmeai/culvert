{{
  config(
    materialized='view',
    tags=['staging', 'application1', 'customers']
  )
}}

/*
  Staging model for Application1 Customers

  Source: odp_em.customers
  Transformations:
  - Clean and standardize fields
  - Add derived columns
*/

with source as (
    select * from {{ source('odp_em', 'customers') }}
    {% if is_incremental() %}
    where _processed_at > (select max(_processed_at) from {{ this }})
    {% endif %}
),

cleaned as (
    select
        -- Primary key
        customer_id,

        -- PII fields
        ssn,
        first_name,
        last_name,
        dob,

        -- Status
        status,
        case status
            when 'A' then 'Active'
            when 'I' then 'Inactive'
            when 'C' then 'Closed'
            else 'Unknown'
        end as status_desc,

        -- Dates
        created_date,

        -- Audit columns
        _run_id,
        _source_file,
        _processed_at,

        -- Derived
        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

