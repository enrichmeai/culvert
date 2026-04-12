{{
  config(
    materialized='incremental',
    unique_key='event_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id', 'account_id'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    require_partition_filter=true,
    tags=['fdp', 'generic', 'event']
  )
}}

/*
  Generic Event Transaction Excess - Foundation Data Product

  JOIN: 2 ODP sources → 1 FDP target
  - odp_generic.customers
  - odp_generic.accounts

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
        c.ssn as ssn_masked,
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
        c._extract_date,
        current_timestamp() as _transformed_at

    from customers c
    inner join accounts a
      on c.customer_id = a.customer_id
      and c._extract_date = a._extract_date

    {% if is_incremental() %}
    where c._processed_at > (
      select coalesce(max(_transformed_at), timestamp('1970-01-01'))
      from {{ this }}
      where _extract_date >= date_sub(current_date(), interval 3 day)
    )
       or a._processed_at > (
      select coalesce(max(_transformed_at), timestamp('1970-01-01'))
      from {{ this }}
      where _extract_date >= date_sub(current_date(), interval 3 day)
    )
    {% endif %}
)

select * from joined
