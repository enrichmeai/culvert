{{
  config(
    materialized='incremental',
    unique_key='portfolio_key',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['customer_id', 'decision_id'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    require_partition_filter=true,
    tags=['fdp', 'generic', 'portfolio']
  )
}}

/*
  Generic Portfolio Account Excess - Foundation Data Product

  MAP: 1 ODP source → 1 FDP target
  - odp_generic.decision

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
        _extract_date,
        current_timestamp() as _transformed_at

    from decisions

    {% if is_incremental() %}
    where _processed_at > (
      select coalesce(max(_transformed_at), timestamp('1970-01-01'))
      from {{ this }}
      where _extract_date >= date_sub(current_date(), interval 3 day)
    )
    {% endif %}
)

select * from mapped
