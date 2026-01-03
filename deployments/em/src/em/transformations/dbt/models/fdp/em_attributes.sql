{{
  config(
    materialized='incremental',
    unique_key='attribute_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id', 'account_id'],
    incremental_strategy='merge',
    on_schema_change='fail',
    tags=['fdp', 'em', 'join']
  )
}}

/*
  EM Attributes - Foundation Data Product

  JOIN: 3 ODP sources → 1 FDP target
  - odp_em.customers
  - odp_em.accounts
  - odp_em.decision

  This model creates a denormalized view of customer attributes
  including their accounts and latest decisions.
*/

with customers as (
    select * from {{ ref('stg_em_customers') }}
),

accounts as (
    select * from {{ ref('stg_em_accounts') }}
),

decisions as (
    select * from {{ ref('stg_em_decision') }}
),

-- Get latest decision per customer
latest_decisions as (
    select
        customer_id,
        decision_id,
        decision_code,
        decision_outcome,
        decision_date,
        score,
        reason_codes,
        row_number() over (
            partition by customer_id
            order by decision_date desc
        ) as rn
    from decisions
),

joined as (
    select
        -- Generate composite key
        {{ dbt_utils.generate_surrogate_key(['c.customer_id', 'a.account_id']) }} as attribute_key,

        -- Customer attributes
        c.customer_id,
        {{ mask_pii('c.ssn', 'ssn') }} as ssn_masked,
        c.first_name,
        c.last_name,
        c.dob as date_of_birth,
        c.status_desc as customer_status,

        -- Account attributes
        a.account_id,
        a.account_type_desc,
        a.balance as current_balance,
        a.open_date as account_open_date,

        -- Decision attributes
        d.decision_id,
        d.decision_outcome,
        cast(d.decision_date as date) as decision_date,
        d.reason_codes as decision_reason,

        -- Audit columns
        c._run_id,
        cast(substr(c._run_id, 5, 8) as date) as _extract_date,
        current_timestamp() as _transformed_ts

    from customers c
    left join accounts a on c.customer_id = a.customer_id
    left join latest_decisions d on c.customer_id = d.customer_id and d.rn = 1

    {% if is_incremental() %}
    where c._processed_at > (select max(_transformed_ts) from {{ this }})
       or a._processed_at > (select max(_transformed_ts) from {{ this }})
    {% endif %}
)

select * from joined

