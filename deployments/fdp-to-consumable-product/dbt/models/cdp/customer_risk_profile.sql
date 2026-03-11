{{
  config(
    materialized='incremental',
    unique_key='risk_profile_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id'],
    incremental_strategy='merge',
    on_schema_change='fail',
    tags=['cdp', 'generic', 'risk']
  )
}}

/*
  Generic Customer Risk Profile — Consumable Data Product

  JOIN: 3 FDP sources → 1 CDP target
  - fdp_generic.event_transaction_excess   (customer + account view)
  - fdp_generic.portfolio_account_excess   (risk decision per customer)
  - fdp_generic.portfolio_account_facility (loan facility per customer)

  This model produces a single, denormalised row per customer that combines
  their transaction exposure, risk decision outcome, and facility details.
  This is the CDP table consumed by the mainframe-segment-transform pipeline
  to produce outbound segment files.
*/

with events as (
    select * from {{ ref('stg_fdp_event_transaction_excess') }}
),

portfolio as (
    select * from {{ ref('stg_fdp_portfolio_account_excess') }}
),

facility as (
    select * from {{ ref('stg_fdp_portfolio_account_facility') }}
),

joined as (
    select
        -- Unique risk profile key (one row per customer per extract date)
        {{ dbt_utils.generate_surrogate_key(['e.customer_id', 'e._extract_date']) }} as risk_profile_key,

        -- Customer identity (from event_transaction_excess)
        e.customer_id,
        e.first_name,
        e.last_name,
        e.date_of_birth,
        e.ssn_masked,
        e.customer_status,

        -- Account exposure (from event_transaction_excess)
        e.account_id,
        e.account_type_desc,
        e.current_balance,
        e.account_open_date,

        -- Risk decision (from portfolio_account_excess)
        p.decision_id,
        p.decision_code,
        p.decision_outcome,
        p.decision_date,
        p.score              as risk_score,
        p.decision_reason,

        -- Facility details (from portfolio_account_facility)
        f.application_id,
        f.loan_amount,
        f.interest_rate,
        f.term_months,
        f.application_date,
        f.application_status as facility_status,
        f.event_type,
        f.account_type,

        -- CDP segment classification (derived)
        case
            when p.decision_outcome = 'APPROVED' and e.current_balance > 0 then 'ACTIVE_APPROVED'
            when p.decision_outcome = 'DECLINED'                            then 'DECLINED'
            when p.decision_outcome = 'REFERRED'                            then 'REFERRED'
            else 'PENDING'
        end as cdp_segment,

        -- Audit columns
        e._run_id,
        e._extract_date,
        current_timestamp() as _cdp_transformed_ts

    from events e
    left join portfolio p on e.customer_id = p.customer_id
    left join facility  f on e.customer_id = f.customer_id

    {% if is_incremental() %}
    where e._transformed_ts > (select max(_cdp_transformed_ts) from {{ this }})
       or p._transformed_ts > (select max(_cdp_transformed_ts) from {{ this }})
       or f._transformed_at > (select max(_cdp_transformed_ts) from {{ this }})
    {% endif %}
)

select * from joined
