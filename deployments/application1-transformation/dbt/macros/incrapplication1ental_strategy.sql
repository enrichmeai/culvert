-- Application2 Blueprint - dbt Macro: Incremental Strategy
--
-- Provides different strategies for incremental loads:
-- - MERGE: Update existing, insert new (recommended)
-- - APPEND_ONLY: Always append (simple but slower)
-- - DELETE_INSERT: Delete+insert partition (good for daily batches)
--
-- Usage in dbt model:
--   {{ config(
--       materialized = 'incremental',
--       on_schema_change = 'fail',
--       incremental_strategy = 'merge',
--       unique_key = 'id'
--   ) }}
--

{% macro build_merge_statement(target_table, source_table, unique_key, update_columns) %}
    MERGE INTO {{ target_table }} T
    USING {{ source_table }} S
    ON T.{{ unique_key }} = S.{{ unique_key }}

    -- Update existing records
    WHEN MATCHED THEN
        UPDATE SET
            {% for column in update_columns %}
                T.{{ column }} = S.{{ column }}
                {%- if not loop.last %}, {% endif %}
            {% endfor %}

    -- Insert new records
    WHEN NOT MATCHED THEN
        INSERT (*)
        VALUES (*)
{% endmacro %}


{% macro build_append_strategy() %}
    -- Simple append: just SELECT all new records
    -- This is the least efficient but simplest approach
    -- Use when:
    --   - Data never changes (immutable)
    --   - Speed is not critical
    --   - Simplicity is preferred

    SELECT *
    FROM {{ source }}
    WHERE run_id = '{{ var("run_id") }}'
{% endmacro %}


{% macro build_delete_insert_strategy(unique_key, date_column) %}
    -- Delete+insert for current partition, then insert new records
    -- Use when:
    --   - Processing daily batches
    --   - Current day's data might be updated
    --   - Historical data is immutable

    DELETE FROM {{ this }}
    WHERE DATE({{ date_column }}) = '{{ run_date }}';

    INSERT INTO {{ this }}
    SELECT * FROM {{ source }}
    WHERE run_id = '{{ var("run_id") }}'
{% endmacro %}


-- Implementation of merge strategy for incremental loads
{% if execute %}
    {% if flags.FULL_REFRESH %}
        -- Full refresh: truncate and reload
        TRUNCATE TABLE {{ this }};
    {% elif var("incremental_strategy") == "merge" %}
        -- Use merge for incremental loads
        {{ build_merge_statement(this, source_data, var("unique_key"), var("update_columns")) }}
    {% elif var("incremental_strategy") == "delete_insert" %}
        -- Use delete+insert for daily batches
        {{ build_delete_insert_strategy(var("unique_key"), var("date_column")) }}
    {% else %}
        -- Default: append only
        INSERT INTO {{ this }}
        {{ build_append_strategy() }}
    {% endif %}
{% endif %}


-- Macro to handle late-arriving data
{% macro handle_late_arriving_data(table, days_lookback) %}
    {% set sql %}
        CREATE OR REPLACE TEMP TABLE late_arrivals AS
        SELECT *
        FROM {{ table }}
        WHERE DATE(processed_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {{ days_lookback }} DAY)
          AND run_id != '{{ var("run_id") }}';

        MERGE INTO {{ table }} T
        USING late_arrivals S
        ON T.id = S.id
        WHEN MATCHED THEN
            UPDATE SET T.* = S.*
        WHEN NOT MATCHED THEN
            INSERT *;
    {% endset %}

    {% do run_query(sql) %}
{% endmacro %}


-- Macro for SCD Type 2 (Slowly Changing Dimension)
{% macro scd2_logic(business_key, change_columns) %}
    SELECT
        {% for col in change_columns %}
            {{ col }},
        {% endfor %}
        CURRENT_TIMESTAMP() as valid_from,
        NULL as valid_to,
        TRUE as is_current,
        ROW_NUMBER() OVER (PARTITION BY {{ business_key }} ORDER BY {{ change_columns | join(", ") }}) as version
    FROM {{ source }}
{% endmacro %}

