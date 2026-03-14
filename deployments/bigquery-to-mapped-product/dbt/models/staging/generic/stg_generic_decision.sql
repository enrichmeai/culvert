{{
  config(
    materialized='view',
    tags=['staging', 'generic', 'decision']
  )
}}

/*
  Staging model for Generic Decision

  Source: odp_generic.decision
  Transformations:
  - Clean and standardize fields
  - Map decision codes to descriptions
*/

with source as (
    select * from {{ source('odp_generic', 'decision') }}
    {% if is_incremental() %}
    where _processed_at > (select max(_processed_at) from {{ this }})
    {% endif %}
),

cleaned as (
    select
        -- Primary key
        decision_id,

        -- Foreign keys
        customer_id,
        application_id,

        -- Decision info
        decision_code,
        case decision_code
            when 'APPROVE' then 'Approved'
            when 'DECLINE' then 'Declined'
            when 'REVIEW' then 'Under Review'
            when 'PENDING' then 'Pending'
            else decision_code
        end as decision_outcome,

        decision_date,
        score,
        reason_codes,

        -- Audit columns
        _run_id,
        _source_file,
        _processed_at,

        -- Derived
        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

