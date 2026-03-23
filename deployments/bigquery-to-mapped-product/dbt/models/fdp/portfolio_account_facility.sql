{{
  config(
    materialized='incremental',
    unique_key='application_id',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['application_id', 'customer_id'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    tags=['fdp', 'generic', 'facility']
  )
}}

/*
    Generic FDP: Portfolio Account Facility

    Transformation: MAP from odp_generic.applications

    Purpose:
    - Facility-focused view of loan applications
    - Maps one ODP source to one FDP target
*/

WITH applications AS (
    SELECT *
    FROM {{ ref('stg_generic_applications') }}
)

SELECT
    -- Application attributes (application_id is the natural key)
    application_id,
    customer_id,
    loan_amount,
    interest_rate,
    term_months,
    application_date,
    application_status,
    event_type,
    account_type,

    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications

{% if is_incremental() %}
WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
{% endif %}
