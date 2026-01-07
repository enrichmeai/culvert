SELECT
    {{ mask_ssn('ssn') }} as ssn_masked,
    {{ mask_ssn_full('ssn') }} as ssn_full_masked,
    {{ mask_account_number('account_number') }} as account_masked,
    {{ mask_email('email') }} as email_masked,
    {{ mask_phone('phone') }} as phone_masked,
    {{ mask_name('first_name', 'last_name') }} as name_masked
FROM {{ ref('test_pii_input') }}
