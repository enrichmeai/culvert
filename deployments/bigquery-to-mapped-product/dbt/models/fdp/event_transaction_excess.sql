{{
  config(
    materialized='incremental',
    unique_key='event_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id', 'account_id'],
    incremental_strategy='merge',
    on_schema_change='fail',
    tags=['fdp', 'generic', 'event']
  )
}}

/*
  Generic Event Transaction Excess - Foundation Data Product

  JOIN: 2 ODP sources → 1 FDP target
  - odp_em.customers
  - odp_em.accounts

  This model joins customer and account data to provide a view of transactions and excesses.
*/

with customers as (
    select * from {{ ref('stg_generic_customers') }}
),

accounts as (
    select * from {{ ref('stg_generic_accounts') }}
),

joined as (
    select
        -- Generate composite key
        {{ dbt_utils.generate_surrogate_key(['c.customer_id', 'a.account_id', 'c._extract_date']) }} as event_key,

        -- Customer attributes
        c.customer_id,
        {{ mask_pii('c.ssn', 'SSN') }} as ssn_masked,
        c.first_name,
        c.last_name,
        c.dob as date_of_birth,
        c.status_desc as customer_status,

        -- Account attributes
        a.account_id,
        a.account_type_desc,
        a.balance as current_balance,
        a.open_date as account_open_date,

        -- Audit columns
        c._run_id,
        cast(substr(c._run_id, 5, 8) as date) as _extract_date,
        current_timestamp() as _transformed_ts

    from customers c
    inner join accounts a on c.customer_id = a.customer_id

    {% if is_incremental() %}
    where c._processed_at > (select max(_transformed_ts) from {{ this }})
       or a._processed_at > (select max(_transformed_ts) from {{ this }})
    {% endif %}
)

select * from joined
