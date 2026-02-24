{{
  config(
    materialized='incremental',
    unique_key='portfolio_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id', 'decision_id'],
    incremental_strategy='merge',
    on_schema_change='fail',
    tags=['fdp', 'generic', 'portfolio']
  )
}}

/*
  Generic Portfolio Account Excess - Foundation Data Product

  MAP: 1 ODP source → 1 FDP target
  - odp_em.decision

  This model maps decision data to portfolio account excess.
*/

with decisions as (
    select * from {{ ref('stg_generic_decision') }}
),

mapped as (
    select
        -- Generate composite key
        {{ dbt_utils.generate_surrogate_key(['decision_id', 'customer_id']) }} as portfolio_key,

        -- Decision/Portfolio attributes
        decision_id,
        customer_id,
        decision_code,
        decision_outcome,
        decision_date,
        score,
        reason_codes as decision_reason,

        -- Audit columns
        _run_id,
        cast(substr(_run_id, 5, 8) as date) as _extract_date,
        current_timestamp() as _transformed_ts

    from decisions

    {% if is_incremental() %}
    where _processed_at > (select max(_transformed_ts) from {{ this }})
    {% endif %}
)

select * from mapped
