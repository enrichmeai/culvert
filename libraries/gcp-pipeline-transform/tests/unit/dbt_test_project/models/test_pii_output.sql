SELECT
    {{ mask_with_suffix('ssn') }} as ssn_masked,
    {{ mask_full('ssn') }} as ssn_full_masked,
    {{ mask_partial_last4('account_number') }} as account_masked,
    {{ mask_email('email') }} as email_masked,
    {{ mask_phone_generic('phone') }} as phone_masked,
    {{ mask_partial_first1('first_name') }} as name_masked
FROM {{ ref('test_pii_input') }}
