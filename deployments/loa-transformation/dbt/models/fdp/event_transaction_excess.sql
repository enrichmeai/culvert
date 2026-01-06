{{
    config(
        materialized='incremental',
        unique_key='event_key',
        schema='fdp_loa',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['application_id', 'event_date'],
        incremental_strategy='merge',
        tags=['fdp', 'loa', 'split']
    )
}}

/*
    LOA FDP 1: Event Transaction Excess
    ===================================

    Transformation: SPLIT from odp_loa.applications
    Filter: Records where event_type IS NOT NULL

    Purpose:
    - Event-focused view of loan applications
    - Contains event lifecycle, transaction details, and excess information

    Key Difference from EM:
    - EM: JOIN 3 entities → 1 FDP table (em_attributes)
    - LOA: SPLIT 1 entity → 2 FDP tables (this is one of them)

    Columns:
    - event_key: Composite key (application_id-event_type-event_date)
    - Event attributes: event_type, event_date, event_status
    - Transaction attributes: transaction_id, amount, date, type
    - Excess attributes: excess_amount, reason, status
*/

WITH applications AS (
    SELECT *
    FROM {{ ref('stg_loa_applications') }}
    WHERE event_type IS NOT NULL  -- Filter for event-related records
)

SELECT
    -- Composite key for uniqueness
    CONCAT(
        application_id, '-',
        COALESCE(event_type, 'NA'), '-',
        COALESCE(CAST(event_date AS STRING), 'NA')
    ) AS event_key,

    -- Application reference
    application_id,

    -- Event attributes
    event_type,
    event_date,
    event_status,

    -- Transaction attributes
    transaction_id,
    transaction_amount,
    transaction_date,
    transaction_type,

    -- Excess attributes
    excess_amount,
    excess_reason,
    excess_status,

    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications

{% if is_incremental() %}
-- Only process new or updated records
WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
{% endif %}

