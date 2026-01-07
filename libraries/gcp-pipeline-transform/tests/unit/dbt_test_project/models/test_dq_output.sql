SELECT
    'val' as some_col
FROM {{ ref('test_pii_input') }}
WHERE 1=0
UNION ALL
{{ generic_not_null_and_unique(ref('test_pii_input'), 'ssn') }}
