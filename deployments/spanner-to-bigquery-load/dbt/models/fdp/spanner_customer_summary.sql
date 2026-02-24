-- Reference Implementation for Spanner-to-FDP (Pattern A: Federated Transformation)
-- This model queries Spanner directly via EXTERNAL_QUERY

{{ config(
    materialized='table',
    labels={
        'entity': 'customer_summary',
        'source': 'spanner'
    }
) }}

WITH spanner_customers AS (
    SELECT * FROM EXTERNAL_QUERY(
        "{{ var('spanner_connection_id') }}",
        """
        SELECT 
            customer_id,
            first_name,
            last_name,
            email,
            membership_level,
            created_at
        FROM {{ var('spanner_table_name') }}
        """
    )
)

SELECT
    customer_id,
    first_name,
    last_name,
    email,
    membership_level,
    -- Apply governance audit columns
    {{ add_audit_columns() }}
FROM spanner_customers
