/*
  Staging: FDP Event Transaction Excess
  Source: fdp_generic.event_transaction_excess (customer + account JOIN from ODP)
*/

with source as (
    select * from {{ source('fdp_generic', 'event_transaction_excess') }}
),

staged as (
    select
        event_key,
        customer_id,
        account_id,
        ssn_masked,
        first_name,
        last_name,
        date_of_birth,
        customer_status,
        account_type_desc,
        current_balance,
        account_open_date,
        _run_id,
        _extract_date,
        _transformed_ts
    from source
)

select * from staged
