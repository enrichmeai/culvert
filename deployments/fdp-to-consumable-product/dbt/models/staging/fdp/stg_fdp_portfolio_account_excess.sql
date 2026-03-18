-- Auto-generated from system.yaml — DO NOT EDIT MANUALLY
-- To modify, update system.yaml and re-run: python generate_dbt_models.py
/*
  Staging: FDP Portfolio Account Excess
  Source: fdp_generic.portfolio_account_excess (decision MAP from ODP)
*/

with source as (
    select * from {{ source('fdp_generic', 'portfolio_account_excess') }}
),

staged as (
    select
        portfolio_key,
        decision_id,
        customer_id,
        decision_code,
        decision_outcome,
        decision_date,
        score,
        decision_reason,
        _run_id,
        _extract_date,
        _transformed_ts
    from source
)

select * from staged
