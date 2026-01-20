-- dbt Macro: Add Audit Columns
-- Adds standard audit columns to any dbt model for data lineage tracking
-- - run_id: Unique run identifier from pipeline
-- - processed_timestamp: When record was processed
-- - source_file: Original source file name
--
-- Usage:
--   {{ add_audit_columns() }}
--

{% macro add_audit_columns() %}
    , '{{ var("run_id") }}' as run_id
    , current_timestamp() as processed_timestamp
    , '{{ var("source_file") }}' as source_file
{% endmacro %}


-- Apply audit columns to a table
{% macro apply_audit_columns(relation) %}
    {% if execute %}
        {% set build_sql %}
            ALTER TABLE {{ relation }}
            ADD COLUMN IF NOT EXISTS run_id STRING,
            ADD COLUMN IF NOT EXISTS processed_timestamp TIMESTAMP,
            ADD COLUMN IF NOT EXISTS source_file STRING;
        {% endset %}

        {% do run_query(build_sql) %}

        {% do log("Audit columns added to " ~ relation, info=true) %}
    {% endif %}
{% endmacro %}


-- Create audit trail from source table
{% macro create_audit_trail(source_table, dest_table) %}
    {% set audit_sql %}
        CREATE OR REPLACE TABLE {{ dest_table }} AS
        SELECT
            *,
            CURRENT_TIMESTAMP() as audit_timestamp,
            CURRENT_USER() as audit_user,
            'INSERT' as audit_action
        FROM {{ source_table }}
        WHERE run_id = '{{ var("run_id") }}';
    {% endset %}

    {% do run_query(audit_sql) %}
{% endmacro %}

