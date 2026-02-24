{{
    config(
        materialized='view',
        schema='stg_loa',
        tags=['staging', 'generic']
    )
}}

/*
    Generic Staging: Applications

    Purpose: Clean view over ODP applications table.
    Source: odp_loa.applications (raw 1:1 mainframe copy)

    Note: Unlike Generic (JOIN 2 sources), Generic will MAP this single source
          into 1 FDP table (portfolio_account_facility)
*/

SELECT
    -- Primary identification
    application_id,
    customer_id,

    -- Application details
    application_date,
    application_type,
    application_status,

    -- Loan details
    loan_amount,
    loan_term,
    interest_rate,

    -- Portfolio attributes (used for portfolio_account_excess FDP)
    portfolio_id,
    portfolio_name,
    portfolio_type,

    -- Account attributes (used for portfolio_account_excess FDP)
    account_id,
    account_number,
    account_type,
    account_status,

    -- Event attributes (used for event_transaction_excess FDP)
    event_type,
    event_date,
    event_status,

    -- Transaction attributes (used for event_transaction_excess FDP)
    transaction_id,
    transaction_amount,
    transaction_date,
    transaction_type,

    -- Excess attributes (used in both FDP tables)
    excess_amount,
    excess_reason,
    excess_status,
    excess_category,
    excess_threshold,

    -- Audit columns
    _run_id,
    _source_file,
    _processed_at,
    _extract_date

FROM {{ source('odp_loa', 'applications') }}

{% if var('extract_date', none) is not none %}
WHERE _extract_date = '{{ var("extract_date") }}'
{% endif %}

