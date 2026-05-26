SELECT
    'dummy' as col
{{ add_audit_columns() }}
FROM {{ ref('test_pii_input') }}
