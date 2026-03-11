/*
  Staging: FDP Portfolio Account Facility
  Source: fdp_generic.portfolio_account_facility (applications MAP from ODP)
*/

with source as (
    select * from {{ source('fdp_generic', 'portfolio_account_facility') }}
),

staged as (
    select
        facility_key,
        application_id,
        customer_id,
        loan_amount,
        interest_rate,
        term_months,
        application_date,
        application_status,
        event_type,
        account_type,
        _run_id,
        _extract_date,
        _transformed_at
    from source
)

select * from staged
