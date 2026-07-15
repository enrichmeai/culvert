-- dbt model example for Spanner to BigQuery Federated Query
-- Pattern: Pattern A (Federated Transformation)

{{ config(
    materialized='incremental',
    unique_key='id',
    incremental_strategy='merge'
) }}

WITH source_data AS (
    SELECT * FROM EXTERNAL_QUERY(
        "{{ var('spanner_connection_id') }}",
        """
        SELECT 
            id,
            column1,
            column2,
            updated_at
        FROM {{ var('spanner_table_name') }}
        """
    )
)

SELECT
    *,
    -- Audit columns required by paved path governance
    '{{ var("run_id") }}' as _run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM source_data

{% if is_incremental() %}
  -- Incremental logic based on Spanner's updated_at
  WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
