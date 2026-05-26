SELECT
    id
    {{ apply_enrichment([
        {'column': 'application_date', 'type': 'DATE_PARTS', 'prefix': 'app'},
        {'column': 'loan_amount', 'type': 'BUCKET', 'buckets': {'<100000': 'Small', '100000-500000': 'Medium', '>500000': 'Large'}, 'target': 'amount_category'},
        {'column': 'status', 'type': 'LOOKUP', 'map': {'A': 'Active', 'I': 'Inactive'}, 'target': 'status_desc'},
        {'column': 'credit_score', 'type': 'EXPRESSION', 'expression': 'CASE WHEN credit_score >= 700 THEN "Good" ELSE "Bad" END', 'target': 'credit_quality'}
    ]) }}
FROM {{ ref('test_pii_input') }}
