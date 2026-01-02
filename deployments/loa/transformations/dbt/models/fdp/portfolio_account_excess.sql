{{
    config(
        materialized='incremental',
        unique_key='portfolio_key',
        schema='fdp_loa',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['portfolio_id', 'account_id'],
        incremental_strategy='merge',
        tags=['fdp', 'loa', 'split']
    )
}}

/*
    LOA FDP 2: Portfolio Account Excess
    ====================================

    Transformation: SPLIT from odp_loa.applications
    Filter: Records where portfolio_id IS NOT NULL

    Purpose:
    - Portfolio-focused view of loan applications
    - Contains portfolio details, account information, and excess thresholds

    Key Difference from EM:
    - EM: JOIN 3 entities → 1 FDP table (em_attributes)
    - LOA: SPLIT 1 entity → 2 FDP tables (this is one of them)

    Columns:
    - portfolio_key: Composite key (portfolio_id-account_id)
    - Portfolio attributes: portfolio_id, portfolio_name, portfolio_type
    - Account attributes: account_id, account_number, account_type, account_status
    - Excess attributes: excess_amount, excess_category, excess_threshold
*/

WITH applications AS (
    SELECT *
    FROM {{ ref('stg_loa_applications') }}
    WHERE portfolio_id IS NOT NULL  -- Filter for portfolio-related records
)

SELECT
    -- Composite key for uniqueness
    CONCAT(
        COALESCE(portfolio_id, 'NA'), '-',
        COALESCE(account_id, 'NA')
    ) AS portfolio_key,

    -- Portfolio attributes
    portfolio_id,
    portfolio_name,
    portfolio_type,

    -- Account attributes
    account_id,
    account_number,
    account_type,
    account_status,

    -- Excess attributes
    excess_amount,
    excess_category,
    excess_threshold,

    -- Application reference
    application_id,

    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications

{% if is_incremental() %}
-- Only process new or updated records
WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
{% endif %}

