{{
  config(
    materialized='incremental',
    unique_key='facility_key',
    schema='fdp_loa',
    partition_by={"field": "_extract_date", "data_type": "date"},
    cluster_by=['application_id', 'customer_id'],
    incremental_strategy='merge',
    tags=['fdp', 'loa', 'facility']
  )
}}

/*
    LOA FDP: Portfolio Account Facility
    ===================================

    Transformation: MAP from odp_loa.applications

    Purpose:
    - Facility-focused view of loan applications
    - Maps one dataset to one ODP and one FDP
*/

WITH applications AS (
    SELECT *
    FROM {{ ref('stg_loa_applications') }}
)

SELECT
    -- Unique key
    application_id AS facility_key,

    -- Application attributes
    application_id,
    customer_id,
    loan_amount,
    interest_rate,
    term_months,
    application_date,
    application_status,
    branch_code,
    product_type,

    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications

{% if is_incremental() %}
-- Only process new or updated records
WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
{% endif %}
