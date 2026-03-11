{{
  config(
    materialized='view',
    tags=['staging', 'generic', 'accounts']
  )
}}

/*
  Staging model for Generic Accounts

  Source: odp_em.accounts
  Transformations:
  - Clean and standardize fields
  - Map account type codes to descriptions
*/

with source as (
    select * from {{ source('odp_generic', 'accounts') }}
    {% if is_incremental() %}
    where _processed_at > (select max(_processed_at) from {{ this }})
    {% endif %}
),

cleaned as (
    select
        -- Primary key
        account_id,

        -- Foreign key
        customer_id,

        -- Account info
        account_type,
        case account_type
            when 'CHECKING' then 'Checking Account'
            when 'SAVINGS' then 'Savings Account'
            when 'MONEY_MARKET' then 'Money Market Account'
            when 'CD' then 'Certificate of Deposit'
            when 'IRA' then 'Individual Retirement Account'
            else account_type
        end as account_type_desc,

        balance,

        -- Status
        status,
        case status
            when 'A' then 'Active'
            when 'I' then 'Inactive'
            when 'C' then 'Closed'
            else 'Unknown'
        end as status_desc,

        -- Dates
        open_date,

        -- Audit columns
        _run_id,
        _source_file,
        _processed_at,

        -- Derived
        current_timestamp() as dbt_updated_at

    from source
)

select * from cleaned

